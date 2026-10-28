"""Bounded #62 session engine, with NO hardware entry point.

Not approved for device use. A future reviewed caller must establish slot/layout,
DA identity, patched host and execution approval before supplying a DA session.
No connect, retry, erase, slot-switch, reboot or generic image/range option exists.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile

from common import sha256_file

ADDRESS, SIZE = 0x13500000, 0x100000
ORIGINAL = '1ebb121adfbac5603dca0e65c3b276a315fda1450bdbd573f3c600b5f399d4b6'
STAGED = '20f35f4368ca7bc1447b459d92e1aacb759245b983cd102f28f524e025972e90'
GUARDS = (
    ('boot_a', 0x11500000, 0x2000000, 'c8cc8244078cb6539c72842540250bc7ca40b8fb9b66123a6bd85a529e47b120'),
    ('rootfs_a', 0x13600000, 0x4000000, '5f0c997ddbc0a8380b4785d58048659f26efff5e7d173825972f3ca45646cc36'),
    ('rootfs_sig_b', 0x1fb00000, 0x100000, ORIGINAL),
    ('misc', 0x700000, 0x100000, 'd8a5b852d2336a8a39a3a09894797de4cd9e14b84425cc12db8d02e4f8cbc780'),
    ('boot_para', 0x8e00000, 0x200000, '11fe64ca9cf44765dc451767b862b5ce4c7759fe38b79fd7949297992e054636'),
)


def run_session(da, original, output, *, mode):
    """Run test (two writes) or restore (one), stopping on the first discrepancy.

    The caller owns/retains the session on failure. Output is a new private run
    directory; its journal is evidence, never authorization to resume automatically.
    """
    if mode not in ('test', 'restore'):
        raise ValueError('mode must be test or restore')
    if not isinstance(original, bytes) or len(original) != SIZE or hashlib.sha256(original).hexdigest() != ORIGINAL:
        raise ValueError('original source identity mismatch')
    if original[0x40000:0x41000] != b'\xff' * 4096:
        raise ValueError('candidate page is not erased in original')
    staged = original[:0x40000] + b'\xaa\x55' * 2048 + original[0x41000:]
    if hashlib.sha256(staged).hexdigest() != STAGED:
        raise ValueError('staged source identity mismatch')
    out = Path(tempfile.mkdtemp(prefix='bounded-restore-', dir=Path(output).resolve()))
    with (out / 'journal.jsonl').open('x') as journal:
        def record(**event):
            journal.write(json.dumps(event) + '\n')
            journal.flush()
            os.fsync(journal.fileno())  # Preserve the attempted-write boundary before USB I/O.

        def check(label, expected):
            for name, addr, size, digest in [('rootfs_sig_a', ADDRESS, SIZE, expected), *GUARDS]:
                path = out / f'{label}-{name}.bin'
                ack = da.readflash(addr=addr, length=size, filename=str(path), parttype=None, display=False)
                length = path.stat().st_size if path.is_file() else None
                actual = sha256_file(path) if length == size else None
                record(read=label, name=name, acknowledged=ack is True, length=length, sha256=actual)
                if ack is not True or length != size or actual != digest:
                    raise ValueError(f'STOP: {label} {name} did not match; no retry or reboot')

        try:
            record(mode=mode, target_offset=ADDRESS, target_length=SIZE)
            check('before', ORIGINAL if mode == 'test' else STAGED)
            steps = [('staged', staged, STAGED), ('original', original, ORIGINAL)] if mode == 'test' else [('original', original, ORIGINAL)]
            for label, data, digest in steps:
                source = out / f'source-{label}.bin'
                with source.open('xb') as stream:
                    stream.write(data)
                source.chmod(0o400)
            for label, _, digest in steps:
                source = out / f'source-{label}.bin'
                if source.stat().st_size != SIZE or sha256_file(source) != digest:
                    raise ValueError('source changed before writing')
                record(write_attempt=label, sha256=digest)
                ack = da.writeflash(addr=ADDRESS, length=SIZE, filename=str(source), parttype=None, display=False)
                record(write_result=label, acknowledged=ack is True)
                if ack is not True:
                    raise ValueError('STOP: write was not acknowledged; no retry or reboot')
                check('after-' + label, digest)
            record(status='ORIGINAL_AND_GUARDS_VERIFIED')
        except BaseException:
            record(status='STOP_UNVERIFIED_NO_RETRY_OR_REBOOT')
            raise
    return out
