"""Block-granular sessions (#113, #114): a sig_a block rehearsal and ordered blockwise misc writes.

Host-tested engine only. The plan is docs/research/misc-probe-plan.md: at most one 256 KiB `misc` erase block is
ever being rewritten, the copy the preloader trusts goes last, and each step re-reads the other blocks and every
neighbor partition. No connect, retry, reboot or slot-switch API. Merging this approves nothing.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile

import slot_session as ss
from common import sha256_file

BLOCK = 0x40000
MISC_ADDR, MISC_SIZE = 0x700000, 0x100000
SIG_ADDR = 0x13500000
PROBE_A_PRIORITY = (0x0d, 0x0c, 0x0b, 0x0a)  # copies 1..4; B stays 0x0f so every copy still selects B
PROBE_SHA = '4c449e543dcea4599deea7867352a0d7592efe07536489a800fd600d74bf51af'  # original misc with the probe priorities


def digest(data):
    return hashlib.sha256(data).hexdigest()


def blocks(image):
    return [image[i * BLOCK:(i + 1) * BLOCK] for i in range(len(image) // BLOCK)]


def probe_image(original):
    """Original misc with a distinct, visible A priority per copy; all copies still select B."""
    out = bytearray(original)
    for k, off in enumerate(ss.MISC_COPIES):
        if original[off:off + 16] != ss.MISC_BEFORE:
            raise ValueError('misc original is not the expected B-selected record')
        out[off + 8] = PROBE_A_PRIORITY[k]
    return bytes(out)


def select_image(original):
    out = bytearray(original)
    for off in ss.MISC_COPIES:
        if original[off:off + 16] != ss.MISC_BEFORE:
            raise ValueError('misc original is not the expected B-selected record')
        out[off:off + 16] = ss.MISC_AFTER
    return bytes(out)


def sig_block_spec(sig_a, k):
    """Identical rewrite of one 256 KiB block of rootfs_sig_a (block 0 holds the certificates: refused)."""
    if k not in (1, 2, 3):
        raise ValueError('block must be 1, 2 or 3; block 0 holds the certificates')
    if len(sig_a) != 0x100000 or digest(sig_a) != ss.ROOTFS_SIG:
        raise ValueError('rootfs_sig_a identity mismatch')
    parts = blocks(sig_a)
    sha = digest(parts[k])
    others = tuple((f'rootfs_sig_a_b{j}', SIG_ADDR + j * BLOCK, BLOCK, digest(parts[j])) for j in range(4) if j != k)
    guards = (*(g for g in ss.COMMON if g[0] != 'rootfs_sig_a'), *others,
              ('misc', MISC_ADDR, MISC_SIZE, ss.MISC_SHA), ('rootfs_a', 0x13600000, 0x4000000, ss.ROOTFS_A_SHA))
    return ss.Spec(f'rootfs_sig_a_b{k}', SIG_ADDR + k * BLOCK, BLOCK, sha, guards, lambda o, c: None, sha, guards), parts[k]


def misc_guards(rootfs_a_ok):
    """Everything outside misc; rootfs_a may be a tuple (stock, candidate) while probing."""
    return (*ss.COMMON, ('rootfs_a', 0x13600000, 0x4000000, rootfs_a_ok))


def run_blockwise(da, before, after, after_sha, order, output, *, mode, guards):
    """mode 'write': before -> after, one erase block per request in `order` (copy numbers 1..4).
    mode 'restore': write the `before` blocks in `order` over any state of the blocks.

    The caller pins `after_sha` (the probe or A-selection image). No retry or reboot; the journal is evidence only.
    """
    if mode not in ('write', 'restore'):
        raise ValueError('mode must be write or restore')
    if len(before) != MISC_SIZE or len(after) != MISC_SIZE or digest(before) != ss.MISC_SHA or digest(after) != after_sha:
        raise ValueError('misc images do not match their pinned hashes')
    if sorted(order) != [1, 2, 3, 4]:
        raise ValueError('order must use each copy 1..4 once')
    if after_sha not in (ss.MISC_A_SHA, PROBE_SHA):
        raise ValueError('after image is neither the pinned selection nor the pinned probe')
    old, new = blocks(before), blocks(after)
    out = Path(tempfile.mkdtemp(prefix=f'misc-blocks-{mode}-', dir=Path(output).resolve()))
    with (out / 'journal.jsonl').open('x') as journal:
        def record(**event):
            journal.write(json.dumps(event) + '\n')
            journal.flush()
            os.fsync(journal.fileno())

        def read(label, name, addr, size):
            path = out / f'{label}-{name}.bin'
            ack = da.readflash(addr=addr, length=size, filename=str(path), parttype=None, display=False)
            length = path.stat().st_size if path.is_file() else None
            actual = sha256_file(path) if length == size else None
            record(read=label, name=name, acknowledged=ack is True, length=length, sha256=actual)
            if ack is not True or length != size:
                raise ValueError(f'STOP: {label} {name} read failed; no retry or reboot')
            return actual

        def check(label, k, target_expect, other_expect):
            got = read(label, f'misc_b{k}', MISC_ADDR + k * BLOCK, BLOCK)
            if target_expect is not None and got != target_expect:
                raise ValueError(f'STOP: {label} misc block {k} did not match; no retry or reboot')
            for j in range(4):
                if j != k and read(label, f'misc_b{j}', MISC_ADDR + j * BLOCK, BLOCK) not in other_expect[j]:
                    raise ValueError(f'STOP: {label} misc block {j} did not match; no retry or reboot')
            for name, addr, size, sha in guards:
                if read(label, name, addr, size) not in ((sha,) if isinstance(sha, str) else sha):
                    raise ValueError(f'STOP: {label} guard {name} did not match; no retry or reboot')

        def write_block(k, data):
            source = out / f'source-b{k}.bin'
            with source.open('xb') as stream:
                stream.write(data)
            source.chmod(0o400)
            if sha256_file(source) != digest(data):
                raise ValueError('source changed before writing')
            record(write_attempt=mode, copy=k + 1, sha256=digest(data))
            ack = da.writeflash(addr=MISC_ADDR + k * BLOCK, length=BLOCK, filename=str(source), parttype=None, display=False)
            record(write_result=mode, copy=k + 1, acknowledged=ack is True)
            if ack is not True:
                raise ValueError('STOP: write was not acknowledged; no retry or reboot')

        try:
            record(mode=mode, target='misc', order=list(order), before_sha=ss.MISC_SHA, after_sha=after_sha)
            if mode == 'write':
                for step, copy in enumerate(order):
                    k = copy - 1
                    done = {c - 1 for c in order[:step]}
                    other = {j: {digest(new[j] if j in done else old[j])} for j in range(4)}
                    check('before', k, digest(old[k]), other)
                    write_block(k, new[k])
                    other[k] = {digest(new[k])}
                    check('after', k, digest(new[k]), other)
            else:
                # Read every block first. Write only blocks that differ from the original, a damaged block (neither
                # original nor new) first; blocks already original are never erased again.
                state = {j: read('plan', f'misc_b{j}', MISC_ADDR + j * BLOCK, BLOCK) for j in range(4)}
                for name, addr, size, sha in guards:
                    if read('plan', name, addr, size) not in ((sha,) if isinstance(sha, str) else sha):
                        raise ValueError(f'STOP: plan guard {name} did not match; no retry or reboot')
                todo = [c for c in order if state[c - 1] != digest(old[c - 1])]
                todo = [c for c in todo if state[c - 1] not in (digest(new[c - 1]),)] + [c for c in todo if state[c - 1] == digest(new[c - 1])]
                record(plan=todo)
                for copy in todo:
                    k = copy - 1
                    check('before', k, state[k], {j: {state[j]} for j in range(4)})
                    write_block(k, old[k])
                    state[k] = digest(old[k])
                    check('after', k, state[k], {j: {state[j]} for j in range(4)})
            final = read('final', 'misc', MISC_ADDR, MISC_SIZE)
            if final != (after_sha if mode == 'write' else ss.MISC_SHA):
                raise ValueError('STOP: final misc image did not match; no retry or reboot')
            record(status='TARGET_AND_GUARDS_VERIFIED')
        except BaseException:
            record(status='STOP_UNVERIFIED_NO_RETRY_OR_REBOOT')
            raise
    return out
