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
LK_A = '0ad94f065ebcfeefd157640d179b1b52779829a85179d07d38dd818b79007156'
TEE_A = '11ff271cde406bd47cd4ded010906b900ccf63bcbdd02e450bec678398400b10'
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
    guards: tuple          # (name, addr, size, sha256) re-read around every write
    validate: Callable     # (original, candidate) -> None, raises ValueError


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


ROOTFS_A = Spec('rootfs_a', 0x13600000, 0x4000000, ROOTFS_A_SHA, (
    ('boot_a', 0x11500000, 0x2000000, BOOT_SHA), ('rootfs_sig_a', 0x13500000, 0x100000, ROOTFS_SIG),
    ('rootfs_sig_b', 0x1fb00000, 0x100000, ROOTFS_SIG), ('misc', 0x700000, 0x100000, MISC_SHA),
    ('boot_para', 0x8e00000, 0x200000, BOOT_PARA), ('lk_a', 0x11200000, 0x200000, LK_A),
    ('tee_a', 0x11400000, 0x100000, TEE_A)), validate_rootfs_a)


def misc_spec(rootfs_a_sha):
    """misc runs after rootfs_a holds the approved candidate, whose hash the caller supplies."""
    return Spec('misc', 0x700000, 0x100000, MISC_SHA, (
        ('boot_a', 0x11500000, 0x2000000, BOOT_SHA), ('rootfs_a', 0x13600000, 0x4000000, rootfs_a_sha),
        ('rootfs_sig_a', 0x13500000, 0x100000, ROOTFS_SIG), ('rootfs_sig_b', 0x1fb00000, 0x100000, ROOTFS_SIG),
        ('boot_para', 0x8e00000, 0x200000, BOOT_PARA), ('lk_a', 0x11200000, 0x200000, LK_A),
        ('tee_a', 0x11400000, 0x100000, TEE_A)), validate_misc)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run_session(da, spec, original, candidate, candidate_sha256, output, *, mode):
    """identical: original over original. write: candidate over original. restore: original over anything.

    The caller owns the session on failure. The journal is evidence, never authority to resume.
    """
    if mode not in ('identical', 'write', 'restore'):
        raise ValueError('mode must be identical, write or restore')
    if not isinstance(original, bytes) or len(original) != spec.size or digest(original) != spec.original_sha:
        raise ValueError('original source identity mismatch')
    if mode == 'write':
        if not isinstance(candidate, bytes) or len(candidate) != spec.size or digest(candidate) != candidate_sha256:
            raise ValueError('candidate differs from the approved hash')
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
            for name, addr, size, sha in spec.guards:
                if read(label, name, addr, size) != sha:
                    raise ValueError(f'STOP: {label} guard {name} did not match; no retry or reboot')

        try:
            record(mode=mode, target=spec.name, target_offset=spec.addr, target_length=spec.size,
                   candidate_sha256=candidate_sha256 if mode == 'write' else None)
            check('before', None if mode == 'restore' else spec.original_sha)
            data, want = (candidate, candidate_sha256) if mode == 'write' else (original, spec.original_sha)
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
