#!/usr/bin/env python3
"""Fake-DA tests only: never import USB or connect to a device."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import changed_restore as r


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.original = b'\xff' * 0x100000
        self.staged = self.original[:0x40000] + b'\xaa\x55' * 2048 + self.original[0x41000:]
        self.hash = lambda data: hashlib.sha256(data).hexdigest()
        patcher = patch.multiple(r, ORIGINAL=self.hash(self.original), STAGED=self.hash(self.staged),
                                GUARDS=tuple((name, addr, 32, self.hash(b'G'*32))
                                             for name, addr, _, _ in r.GUARDS))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.data = {r.ADDRESS: self.original, **{a: b'G'*32 for _, a, _, _ in r.GUARDS}}
        self.writes = []
        self.fail_write = self.fail_read = self.exception = self.corrupt_guard = self.corrupt_target = 0
        self.shape = None

    def readflash(self, addr, length, filename, **kwargs):
        data = self.data[addr]
        if self.shape == 'short':
            data = data[:-1]
        if self.shape == 'long':
            data += b'X'
        Path(filename).write_bytes(data)
        return False if self.fail_read == len(self.writes)+1 else True

    def writeflash(self, addr, length, filename, **kwargs):
        self.writes.append((addr, length))
        if self.exception == len(self.writes):
            raise OSError('lost USB')
        self.data[addr] = Path(filename).read_bytes()
        if self.corrupt_guard == len(self.writes):
            self.data[r.GUARDS[0][1]] = b'X'*32
        if self.corrupt_target == len(self.writes):
            self.data[addr] = b'X'*length
        return False if self.fail_write == len(self.writes) else True

    def run_session(self, mode='test'):
        return r.run_session(self, self.original, self.out, mode=mode)

    def test_stage_then_restore_exact_original(self):
        self.run_session()
        self.assertEqual(self.writes, [(r.ADDRESS, r.SIZE)]*2)
        self.assertEqual(self.data[r.ADDRESS], self.original)

    def test_restore_only_accepts_staged_target(self):
        self.data[r.ADDRESS] = self.staged
        self.run_session('restore')
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(self.data[r.ADDRESS], self.original)

    def test_unknown_target_or_wrong_mode_cannot_write(self):
        for mode, data in [('test', self.staged), ('restore', self.original), ('test', b'X'*r.SIZE)]:
            self.data[r.ADDRESS] = data
            with self.assertRaises(ValueError):
                self.run_session(mode)
        self.assertEqual(self.writes, [])

    def test_changed_guard_blocks_first_write(self):
        self.data[r.GUARDS[-1][1]] = b'X'*32
        with self.assertRaises(ValueError):
            self.run_session()
        self.assertEqual(self.writes, [])

    def test_bad_source_and_mode_cannot_write(self):
        for source, mode in [(b'X'*r.SIZE, 'test'), (self.original[:-1], 'test'), (self.original, 'anything')]:
            with self.assertRaises(ValueError):
                r.run_session(self, source, self.out, mode=mode)
        self.assertEqual(self.writes, [])

    def test_false_ack_never_restores_or_retries_even_if_bytes_match(self):
        self.fail_write = 1
        with self.assertRaises(ValueError):
            self.run_session()
        self.assertEqual(len(self.writes), 1)

    def test_bad_lengths_or_false_read_block_write(self):
        for shape in ('short', 'long', None):
            self.shape = shape
            self.fail_read = 1 if shape is None else 0
            with self.assertRaises(ValueError):
                self.run_session()
        self.assertEqual(self.writes, [])

    def assert_stopped_after_stage(self):
        with self.assertRaises((ValueError, OSError)):
            self.run_session()
        self.assertEqual(len(self.writes), 1)

    def test_stage_exception_never_restores(self):
        self.exception = 1
        self.assert_stopped_after_stage()

    def test_changed_post_stage_guard_never_restores(self):
        self.corrupt_guard = 1
        self.assert_stopped_after_stage()

    def test_wrong_staged_readback_never_restores(self):
        self.corrupt_target = 1
        self.assert_stopped_after_stage()

    def test_failed_post_stage_read_never_restores(self):
        self.fail_read = 2
        self.assert_stopped_after_stage()

    def test_corrupt_final_readback_is_not_success(self):
        self.corrupt_target = 2
        with self.assertRaises(ValueError):
            self.run_session()
        self.assertEqual(len(self.writes), 2)

    def test_journal_has_attempts_and_verified_end(self):
        out = self.run_session()
        events = [json.loads(line) for line in (out / 'journal.jsonl').read_text().splitlines()]
        self.assertEqual([e['write_attempt'] for e in events if 'write_attempt' in e], ['staged', 'original'])
        self.assertEqual(events[-1]['status'], 'ORIGINAL_AND_GUARDS_VERIFIED')
        self.assertEqual(len([e for e in events if 'read' in e]), 18)

    def test_restore_only_still_requires_matching_guards(self):
        self.data[r.ADDRESS] = self.staged
        self.data[r.GUARDS[-1][1]] = b'X'*32
        with self.assertRaises(ValueError):
            self.run_session('restore')
        self.assertEqual(self.writes, [])

    def test_failed_session_journal_never_claims_verification(self):
        self.exception = 1
        with self.assertRaises(OSError):
            self.run_session()
        journal = next(self.out.glob('bounded-restore-*/journal.jsonl'))
        events = [json.loads(line) for line in journal.read_text().splitlines()]
        self.assertEqual(events[-1]['status'], 'STOP_UNVERIFIED_NO_RETRY_OR_REBOOT')
        self.assertEqual(len([e for e in events if 'write_attempt' in e]), 1)

    def test_original_source_creation_failure_cannot_strand_staged_data(self):
        original_open = Path.open
        def fail_original(path, *args, **kwargs):
            if path.name == 'source-original.bin':
                raise OSError('disk full')
            return original_open(path, *args, **kwargs)
        with patch.object(Path, 'open', fail_original), self.assertRaises(OSError):
            self.run_session()
        self.assertEqual(self.writes, [])

    def test_restore_failure_is_not_reported_as_success(self):
        self.fail_write = 2
        with self.assertRaises(ValueError):
            self.run_session()
        self.assertEqual(len(self.writes), 2)


if __name__ == '__main__':
    unittest.main()
