#!/usr/bin/env python3
"""Fake-DA tests only: never import USB or connect to a device."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import slot_session as s

H = lambda data: hashlib.sha256(data).hexdigest()


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.original = b'\x11' * 64
        self.candidate = b'\x22' * 64
        self.guard = b'G' * 16
        guards = tuple((f'g{i}', 0x2000 + i * 0x100, 16, H(self.guard)) for i in range(3))
        # g2 may legitimately differ after a fallback repair, but only when restoring
        wide = guards[:2] + (('g2', 0x2200, 16, (H(self.guard), H(b'R' * 16))),)
        self.spec = s.Spec('t', 0x1000, 64, H(self.original), guards,
                           lambda o, c: None if c != o else (_ for _ in ()).throw(ValueError('same')),
                           H(self.candidate), wide)
        self.data = {0x1000: self.original, **{0x2000 + i * 0x100: self.guard for i in range(3)}}
        self.writes = []
        self.fail_write = self.fail_read = self.drift_guard = self.corrupt = self.exception = 0
        self.reads = 0

    def readflash(self, addr, length, filename, **kw):
        self.reads += 1
        Path(filename).write_bytes(self.data[addr])
        return False if self.fail_read == self.reads else True

    def writeflash(self, addr, length, filename, **kw):
        self.writes.append((addr, length))
        if self.exception:
            raise OSError('lost USB')
        self.data[addr] = Path(filename).read_bytes()
        if self.drift_guard:
            self.data[0x2000] = b'X' * 16
        if self.corrupt:
            self.data[addr] = b'X' * length
        return False if self.fail_write else True

    def run_(self, mode='write', **kw):
        return s.run_session(self, self.spec, kw.get('original', self.original), kw.get('candidate', self.candidate),
                             self.out, mode=mode)

    def journal(self):
        return [json.loads(l) for p in self.out.glob('*/journal.jsonl') for l in p.read_text().splitlines()]

    def test_identical_writes_original_once_and_verifies(self):
        self.run_('identical')
        self.assertEqual(self.writes, [(0x1000, 64)])
        self.assertEqual(self.data[0x1000], self.original)

    def test_write_puts_candidate_and_checks_everything_after(self):
        self.run_('write')
        self.assertEqual(self.data[0x1000], self.candidate)
        reads = [e for e in self.journal() if 'read' in e]
        self.assertEqual([e['read'] for e in reads], ['before'] * 4 + ['after'] * 4)

    def test_restore_works_from_candidate_or_a_half_written_target(self):
        for state in (self.candidate, b'\x33' * 64):
            self.data[0x1000] = state
            self.run_('restore', candidate=None)
            self.assertEqual(self.data[0x1000], self.original)

    def test_restore_still_stops_on_guard_drift(self):
        self.data[0x1000] = self.candidate
        self.data[0x2100] = b'X' * 16
        with self.assertRaises(ValueError):
            self.run_('restore', candidate=None)
        self.assertEqual(self.writes, [])

    def test_wrong_inputs_refuse_before_any_io(self):
        for kw in ({'original': b'\x00' * 64}, {'candidate': b'\x55' * 64}, {'candidate': self.original}):
            with self.assertRaises(ValueError):
                self.run_('write', **kw)
        with self.assertRaises(ValueError):
            self.run_('erase')
        self.assertEqual((self.writes, self.reads), ([], 0))

    def test_before_mismatch_target_or_guard_stops_without_writing(self):
        self.data[0x1000] = b'\x44' * 64
        with self.assertRaises(ValueError):
            self.run_('write')
        self.data[0x1000] = self.original
        self.data[0x2200] = b'X' * 16
        with self.assertRaises(ValueError):
            self.run_('write')
        self.assertEqual(self.writes, [])

    def test_failures_stop_and_journal_unverified_without_retry(self):
        for attr in ('fail_write', 'drift_guard', 'corrupt', 'exception'):
            self.setUp()
            setattr(self, attr, 1)
            with self.assertRaises((ValueError, OSError), msg=attr):
                self.run_('write')
            self.assertEqual(len(self.writes), 1, attr)
            self.assertEqual(self.journal()[-1]['status'], 'STOP_UNVERIFIED_NO_RETRY_OR_REBOOT')

    def test_read_failure_stops_before_the_write(self):
        self.fail_read = 2
        with self.assertRaises(ValueError):
            self.run_('write')
        self.assertEqual(self.writes, [])

    def test_restore_accepts_a_repaired_guard_but_write_does_not(self):
        self.data[0x2200] = b'R' * 16
        with self.assertRaises(ValueError):
            self.run_('write')
        self.assertEqual(self.writes, [])
        self.data[0x1000] = self.candidate
        self.run_('restore', candidate=None)
        self.assertEqual(self.data[0x1000], self.original)

    def test_write_intent_is_journaled_and_fsynced_before_the_write(self):
        order = []
        real_fsync = s.os.fsync
        s.os.fsync = lambda fd: (order.append('fsync'), real_fsync(fd))[1]
        self.addCleanup(setattr, s.os, 'fsync', real_fsync)
        real_write = self.writeflash
        self.writeflash = lambda **kw: (order.append('write'), real_write(**kw))[1]
        self.run_('write')
        attempt = [e for e in self.journal() if 'write_attempt' in e]
        self.assertEqual(len(attempt), 1)
        self.assertEqual(order[order.index('write') - 1], 'fsync')

    def test_source_file_is_read_only_and_new_run_dir_each_time(self):
        a = self.run_('identical')
        self.assertEqual((a / 'source.bin').stat().st_mode & 0o222, 0)
        self.assertNotEqual(a, self.run_('identical'))


class SpecTests(unittest.TestCase):
    def test_misc_candidate_must_be_exactly_the_four_copy_selection(self):
        original = bytearray(b'\xff' * 0x100000)
        for off in s.MISC_COPIES:
            original[off:off + 16] = s.MISC_BEFORE
        good = bytearray(original)
        for off in s.MISC_COPIES:
            good[off:off + 16] = s.MISC_AFTER
        s.validate_misc(bytes(original), bytes(good))
        for tweak in (lambda b: b.__setitem__(0x40800 + 8, 0x0e), lambda b: b.__setitem__(0x1000, 0), lambda b: b.__setitem__(slice(0xc0800, 0xc0810), s.MISC_BEFORE)):
            bad = bytearray(good)
            tweak(bad)
            with self.assertRaises(ValueError):
                s.validate_misc(bytes(original), bytes(bad))
        with self.assertRaises(ValueError):
            s.validate_misc(b'\xff' * 0x100000, bytes(good))

    def test_misc_selection_changes_four_bytes_per_copy(self):
        diff = [i for i, (a, b) in enumerate(zip(s.MISC_BEFORE, s.MISC_AFTER)) if a != b]
        self.assertEqual(diff, [8, 9, 10, 12])

    def test_rootfs_a_candidate_must_be_a_valid_different_ubi(self):
        with self.assertRaises(ValueError):
            s.validate_rootfs_a(b'\xff' * 0x4000000, b'\xff' * 0x4000000)
        with self.assertRaises(ValueError):
            s.validate_rootfs_a(b'\xff' * 0x4000000, b'\x00' * 0x4000000)
        with self.assertRaises(ValueError):
            s.validate_rootfs_a(b'\xff' * 0x4000000, b'short')

    def specs(self):
        return s.rootfs_a_spec('a' * 64), s.misc_spec('a' * 64)

    def test_real_specs_guard_both_slots_and_never_the_target(self):
        every = {'boot_a', 'rootfs_sig_a', 'rootfs_sig_b', 'boot_para', 'lk_a', 'tee_a', 'boot_b', 'rootfs_b', 'lk_b', 'tee_b',
                 'proinfo', 'md1dsp_a', 'md1dsp_b', 'mcf1_a', 'mcf1_b', 'mcf2_a', 'mcf2_b'}
        rootfs_a, misc = self.specs()
        self.assertEqual({g[0] for g in rootfs_a.guards}, every | {'misc'})
        self.assertEqual({g[0] for g in misc.guards}, every | {'rootfs_a'})
        for spec in (rootfs_a, misc):
            self.assertNotIn(spec.name, {g[0] for g in spec.guards})
            ranges = sorted((g[1], g[1] + g[2]) for g in (*spec.guards, (spec.name, spec.addr, spec.size)))
            for (a0, a1), (b0, b1) in zip(ranges, ranges[1:]):
                self.assertLessEqual(a1, b0, 'overlapping ranges')

    def test_hashes_are_pinned_and_a_new_rootfs_a_hash_is_required(self):
        rootfs_a, misc = self.specs()
        self.assertEqual((rootfs_a.candidate_sha, misc.candidate_sha), ('a' * 64, s.MISC_A_SHA))
        for bad in ('short', s.ROOTFS_A_SHA, s.ROOTFS_B_SHA):
            with self.assertRaises(ValueError):
                s.rootfs_a_spec(bad)
            with self.assertRaises(ValueError):
                s.misc_spec(bad)

    def test_rootfs_a_restore_needs_misc_on_b_but_misc_restore_tolerates_a_repaired_rootfs_a(self):
        rootfs_a, misc = self.specs()
        self.assertEqual(dict((g[0], g[3]) for g in rootfs_a.restore_guards)['misc'], s.MISC_SHA)
        accepted = dict((g[0], g[3]) for g in misc.restore_guards)['rootfs_a']
        self.assertEqual(set(accepted), {'a' * 64, s.ROOTFS_A_SHA, s.ROOTFS_B_SHA})
        self.assertEqual(dict((g[0], g[3]) for g in misc.guards)['rootfs_a'], 'a' * 64)

    def test_misc_candidate_hash_matches_the_selection_bytes(self):
        original = bytearray(b'\xff' * 0x100000)
        for off in s.MISC_COPIES:
            original[off:off + 16] = s.MISC_BEFORE
        for off in s.MISC_COPIES:
            original[off:off + 16] = s.MISC_AFTER
        # the real dump's other bytes are 0xff, so this reproduces the pinned hash
        self.assertEqual(H(bytes(original)), s.MISC_A_SHA)


if __name__ == '__main__':
    unittest.main()
