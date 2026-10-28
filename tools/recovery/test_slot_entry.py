#!/usr/bin/env python3
"""Offline tests of the entry gates; no hardware, SSH, USB or private data."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import sys

import slot_entry as e

IDENT = {'target': 'rootfs_a', 'original': 'o' * 64, 'candidate': 'c' * 64, 'da': 'd' * 64, 'tools': 't' * 64, 'unit': 'u' * 64}


class PriorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def make(self, mode='identical', status='VERIFIED', target='rootfs_a', attempts=None, final='TARGET_AND_GUARDS_VERIFIED', age=0, ident=IDENT):
        self.n = getattr(self, 'n', 0) + 1
        run = (self.root / f'{target}-{mode}-{self.n}').resolve()
        (run / 'inner').mkdir(parents=True, exist_ok=True)
        events = [{'mode': mode}] + [{'write_attempt': a} for a in (attempts if attempts is not None else [mode])] + [{'status': final}]
        journal = run / 'inner' / 'journal.jsonl'
        journal.write_text(''.join(json.dumps(x) + '\n' for x in events))
        receipt = {'schema': 2, 'run': str(run), 'target': target, 'mode': mode, 'status': status, 'identity': ident,
                   'created': time.time() - age, 'journal': 'inner/journal.jsonl', 'journal_hash': e.digest(journal.read_bytes())}
        (run / 'receipt.json').write_text(json.dumps(receipt))
        return run

    def test_good_verified_prior_is_accepted(self):
        e.load_prior(self.make(), IDENT, 'rootfs_a', 'identical', True)

    def test_each_binding_failure_is_refused(self):
        cases = {
            'stale': dict(age=90000),
            'unverified': dict(status='STOP_UNVERIFIED'),
            'other image': dict(ident={**IDENT, 'candidate': 'x' * 64}),
            'other unit': dict(ident={**IDENT, 'unit': 'x' * 64}),
            'two writes': dict(attempts=['identical', 'identical']),
            'wrong write': dict(attempts=['write']),
            'no final verify': dict(final='STOP_UNVERIFIED_NO_RETRY_OR_REBOOT'),
        }
        for name, kw in cases.items():
            with self.assertRaises(ValueError, msg=name):
                e.load_prior(self.make(**kw), IDENT, 'rootfs_a', 'identical', True)

    def test_edited_journal_or_wrong_mode_or_target_is_refused(self):
        run = self.make()
        (run / 'inner' / 'journal.jsonl').write_text('{"tampered": 1}\n')
        with self.assertRaises(ValueError):
            e.load_prior(run, IDENT, 'rootfs_a', 'identical', True)
        run = self.make()
        for target, mode in (('misc', 'identical'), ('rootfs_a', 'write')):
            with self.assertRaises(ValueError):
                e.load_prior(run, IDENT, target, mode, True)

    def test_resume_accepts_a_stopped_write_once(self):
        run = self.make('write', status='STOP_UNVERIFIED', final='STOP_UNVERIFIED_NO_RETRY_OR_REBOOT')
        e.load_prior(run, IDENT, 'rootfs_a', 'write', False)
        (run / 'restore-claim.json').write_text('{}')
        with self.assertRaises(ValueError):
            e.load_prior(run, IDENT, 'rootfs_a', 'write', False)

    def test_consumed_restore_run_is_not_resumable(self):
        run = self.make('write', status='RESTORE_ATTEMPTED', final='STOP_UNVERIFIED_NO_RETRY_OR_REBOOT')
        with self.assertRaises(ValueError):
            e.load_prior(run, IDENT, 'rootfs_a', 'write', False)

    def test_a_write_that_never_started_has_nothing_to_resume(self):
        run = self.make('write', status='STOP_UNVERIFIED', attempts=[], final='STOP_UNVERIFIED_NO_RETRY_OR_REBOOT')
        with self.assertRaises(ValueError):
            e.load_prior(run, IDENT, 'rootfs_a', 'write', False)


class GateTests(unittest.TestCase):
    def run_main(self, *argv):
        with patch.object(sys, 'argv', ['slot_entry.py', *argv]):
            e.main()

    def test_sequencing_table(self):
        flags = lambda t, m: [p[0] for p in e.PRIOR[(t, m)]]
        self.assertEqual(flags('rootfs_a', 'identical'), [])
        self.assertEqual(flags('rootfs_a', 'write'), ['prior_identical'])
        self.assertEqual(sorted(flags('misc', 'write')), ['prior_identical', 'prior_rootfs_a'])
        self.assertEqual(flags('misc', 'identical'), ['prior_rootfs_a'])
        self.assertEqual((flags('rootfs_a', 'restore'), flags('misc', 'restore')), (['resume'], ['resume']))
        self.assertTrue(all(p[3] for k, v in e.PRIOR.items() if k[1] != 'restore' for p in v))
        self.assertTrue(all(not p[3] for k, v in e.PRIOR.items() if k[1] == 'restore' for p in v))

    def test_missing_or_misplaced_prior_flags_refuse_before_touching_data(self):
        for argv in (('rootfs_a', 'write'), ('misc', 'write', '--prior-identical', '/x'), ('misc', 'restore'),
                     ('rootfs_a', 'identical', '--resume', '/x'), ('rootfs_a', 'write', '--prior-identical', '/x', '--prior-rootfs-a', '/y'),
                     ('misc', 'identical', '--resume', '/x', '--prior-rootfs-a', '/y')):
            with self.assertRaises(ValueError, msg=argv):
                self.run_main(*argv)

    def test_phrase_names_target_mode_image_and_hazards(self):
        self.assertEqual(e.phrase('rootfs_a', 'write', 'abcdef1234567890', False), 'WRITE write rootfs_a abcdef123456')
        self.assertIn('SAME-DISK', e.phrase('rootfs_a', 'write', 'a' * 64, True))
        self.assertTrue(e.phrase('misc', 'identical', 'a' * 64, False).endswith('BROM-ROUTE-PROVEN'))
        self.assertNotIn('BROM', e.phrase('rootfs_a', 'identical', 'a' * 64, False))


if __name__ == '__main__':
    unittest.main()
