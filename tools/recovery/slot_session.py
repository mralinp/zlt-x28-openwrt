"""Bounded rootfs_a / misc session engine (#99, #100). Host-tested only; no entry CLI yet.

One write of a pre-approved image to one fixed partition, with every neighbor re-read before and after.
No connect, retry, erase, slot-switch, reboot or generic image/range option exists. Device use needs the
attested entry command and separate approval; merging this file approves nothing. See
docs/research/rootfs-a-write-plan.md.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Callable, NamedTuple

from common import sha256_file

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build'))
from package_ubi import inspect as inspect_ubi

ROOTFS_SIG = '1ebb121adfbac5603dca0e65c3b276a315fda1450bdbd573f3c600b5f399d4b6'
MISC_SHA = 'd8a5b852d2336a8a39a3a09894797de4cd9e14b84425cc12db8d02e4f8cbc780'
ROOTFS_A_SHA = '5f0c997ddbc0a8380b4785d58048659f26efff5e7d173825972f3ca45646cc36'
BOOT_SHA = 'c8cc8244078cb6539c72842540250bc7ca40b8fb9b66123a6bd85a529e47b120'
# Live stock B writes its overlay into the last 127 erase blocks of rootfs_b; only the first 128 blocks (32 MiB) are static.
ROOTFS_B_HEAD_SHA = '33ef0fc046592bf2ef64c1604c829252013a6c656c66cf2b903d92ef5fb648b6'
ROOTFS_B_SHA = 'c4e3f3d25b3aefca70995c070faa177931a61738b4997acd52a6446daee4cf01'
MISC_A_SHA = 'cd512c873dd4bf290135989e6da4b4b542e277ea2c01239f331ddccae253a543'  # original with the four-copy A selection
LK_A = '0ad94f065ebcfeefd157640d179b1b52779829a85179d07d38dd818b79007156'
TEE_A = '11ff271cde406bd47cd4ded010906b900ccf63bcbdd02e450bec678398400b10'  # A and B copies of boot/lk/tee/rootfs_sig are byte-identical
BOOT_PARA = '11fe64ca9cf44765dc451767b862b5ce4c7759fe38b79fd7949297992e054636'

# Per-copy A-selection edit from docs/research/slot-selection.md; copies sit one 256 KiB erase block apart.
MISC_BEFORE = bytes.fromhex('00414230ffffffff0e0001000f000100')
MISC_AFTER = bytes.fromhex('00414230ffffffff0f0300000e000100')
MISC_COPIES = tuple(0x800 + k * 0x40000 for k in range(4))


class Spec(NamedTuple):
    name: str
    addr: int
    size: int
    original_sha: str
    guards: tuple          # (name, addr, size, sha256 or tuple of accepted sha256) re-read around every write
    validate: Callable     # (original, candidate) -> None, raises ValueError
    candidate_sha: str     # the only image `write` may put on the target (pinned by whoever builds the spec)
    restore_guards: tuple  # guards for `restore`: wider, because stock B may have repaired slot A after a fallback


def validate_rootfs_a(original, candidate):
    if len(candidate) != 0x4000000 or candidate == original:
        raise ValueError('rootfs_a candidate must be a different 64 MiB image')
    inspect_ubi(candidate)  # UBI headers, volumes, geometry and SquashFS/UBIFS checks from the build tooling


def validate_misc(original, candidate):
    expected = bytearray(original)
    for off in MISC_COPIES:
        if original[off:off + 16] != MISC_BEFORE:
            raise ValueError('misc original is not the expected B-selected record')
        expected[off:off + 16] = MISC_AFTER
    if bytes(expected) != candidate:
        raise ValueError('misc candidate is not exactly the four-copy A selection')


B_SIDE = (('boot_b', 0x1db00000, 0x2000000, BOOT_SHA), ('rootfs_b', 0x1fc00000, 0x2000000, ROOTFS_B_HEAD_SHA),
          ('lk_b', 0x1d800000, 0x200000, LK_A), ('tee_b', 0x1da00000, 0x100000, TEE_A))
# Static modem-side partitions (identical A/B copies); the 80 MiB md1img pair and the live nvdata/nvram are not re-read.
MODEM_SIDE = (('proinfo', 0x600000, 0x100000, 'f5fb04aa5b882706b9309e885f19477261336ef76a150c3b4d3489dfac3953ec'), ('md1dsp_a', 0x10000000, 0xa00000, '1bfda52e00b6a792e4b2c47abb7d7efc3ed5cea8f97e4dcd18e816b0e758bbb0'), ('md1dsp_b', 0x1c600000, 0xa00000, '1bfda52e00b6a792e4b2c47abb7d7efc3ed5cea8f97e4dcd18e816b0e758bbb0'),
              ('mcf1_a', 0x6d00000, 0x800000, 'c01bb4545be6644cb666943b501d20ecc447208b25ad06879e7a29bb70c32351'), ('mcf1_b', 0x7d00000, 0x800000, 'c01bb4545be6644cb666943b501d20ecc447208b25ad06879e7a29bb70c32351'),
              ('mcf2_a', 0x7500000, 0x800000, '6762592011405cc420e001697b0d245b8a01871f7934f2b132b4ca9d231bd154'), ('mcf2_b', 0x8500000, 0x800000, '6762592011405cc420e001697b0d245b8a01871f7934f2b132b4ca9d231bd154'))
COMMON = (('boot_a', 0x11500000, 0x2000000, BOOT_SHA), ('rootfs_sig_a', 0x13500000, 0x100000, ROOTFS_SIG),
          ('rootfs_sig_b', 0x1fb00000, 0x100000, ROOTFS_SIG), ('boot_para', 0x8e00000, 0x200000, BOOT_PARA),
          ('lk_a', 0x11200000, 0x200000, LK_A), ('tee_a', 0x11400000, 0x100000, TEE_A), *B_SIDE, *MODEM_SIDE)


def rootfs_a_spec(candidate_sha):
    """Write rootfs_a. `restore` is refused unless misc still selects B: restore misc first once A is selected."""
    if len(candidate_sha) != 64 or candidate_sha in (ROOTFS_A_SHA, ROOTFS_B_SHA):
        raise ValueError('rootfs_a candidate hash must be a new SHA-256')
    guards = (*COMMON, ('misc', 0x700000, 0x100000, MISC_SHA))
    return Spec('rootfs_a', 0x13600000, 0x4000000, ROOTFS_A_SHA, guards, validate_rootfs_a, candidate_sha, guards)


def misc_spec(rootfs_a_sha):
    """Select A (write) or return to B (restore). misc is a live, whole-partition (1 MiB) erase and rewrite."""
    if len(rootfs_a_sha) != 64 or rootfs_a_sha in (ROOTFS_A_SHA, ROOTFS_B_SHA):
        raise ValueError('misc session needs the approved new rootfs_a hash')
    rootfs_a = ('rootfs_a', 0x13600000, 0x4000000)
    # After a fallback, stock B's ab_image_sync may have copied B over A: rootfs_a then equals rootfs_b.
    return Spec('misc', 0x700000, 0x100000, MISC_SHA, (*COMMON, (*rootfs_a, rootfs_a_sha)), validate_misc, MISC_A_SHA,
                (*COMMON, (*rootfs_a, (rootfs_a_sha, ROOTFS_A_SHA, ROOTFS_B_SHA))))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run_session(da, spec, original, candidate, output, *, mode):
    """identical: original over original. write: candidate over original. restore: original over anything.

    The caller owns the session on failure. The journal is evidence, never authority to resume.
    """
    if mode not in ('identical', 'write', 'restore'):
        raise ValueError('mode must be identical, write or restore')
    if not isinstance(original, bytes) or len(original) != spec.size or digest(original) != spec.original_sha:
        raise ValueError('original source identity mismatch')
    if mode == 'write':
        if not isinstance(candidate, bytes) or len(candidate) != spec.size or digest(candidate) != spec.candidate_sha:
            raise ValueError('candidate differs from the hash pinned in the spec')
        spec.validate(original, candidate)
    out = Path(tempfile.mkdtemp(prefix=f'{spec.name}-{mode}-', dir=Path(output).resolve()))
    with (out / 'journal.jsonl').open('x') as journal:
        def record(**event):
            journal.write(json.dumps(event) + '\n')
            journal.flush()
            os.fsync(journal.fileno())  # Preserve the attempted-write boundary before USB I/O.

        def read(label, name, addr, size):
            path = out / f'{label}-{name}.bin'
            ack = da.readflash(addr=addr, length=size, filename=str(path), parttype=None, display=False)
            length = path.stat().st_size if path.is_file() else None
            actual = sha256_file(path) if length == size else None
            record(read=label, name=name, acknowledged=ack is True, length=length, sha256=actual)
            if ack is not True or length != size:
                raise ValueError(f'STOP: {label} {name} read failed; no retry or reboot')
            return actual

        def check(label, expected_target):
            # restore tolerates any target state (an interrupted write); everything else must match exactly.
            actual = read(label, spec.name, spec.addr, spec.size)
            if expected_target is not None and actual != expected_target:
                raise ValueError(f'STOP: {label} {spec.name} did not match; no retry or reboot')
            for name, addr, size, sha in (spec.restore_guards if mode == 'restore' else spec.guards):
                if read(label, name, addr, size) not in ((sha,) if isinstance(sha, str) else sha):
                    raise ValueError(f'STOP: {label} guard {name} did not match; no retry or reboot')

        try:
            record(mode=mode, target=spec.name, target_offset=spec.addr, target_length=spec.size,
                   candidate_sha256=spec.candidate_sha if mode == 'write' else None)
            check('before', None if mode == 'restore' else spec.original_sha)
            data, want = (candidate, spec.candidate_sha) if mode == 'write' else (original, spec.original_sha)
            source = out / 'source.bin'
            with source.open('xb') as stream:
                stream.write(data)
            source.chmod(0o400)
            if source.stat().st_size != spec.size or sha256_file(source) != want:
                raise ValueError('source changed before writing')
            record(write_attempt=mode, sha256=want)
            ack = da.writeflash(addr=spec.addr, length=spec.size, filename=str(source), parttype=None, display=False)
            record(write_result=mode, acknowledged=ack is True)
            if ack is not True:
                raise ValueError('STOP: write was not acknowledged; no retry or reboot')
            check('after', want)
            record(status='TARGET_AND_GUARDS_VERIFIED')
        except BaseException:
            record(status='STOP_UNVERIFIED_NO_RETRY_OR_REBOOT')
            raise
    return out
