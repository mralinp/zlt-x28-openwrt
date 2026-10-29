#!/usr/bin/env python3
"""Offline tests of the block-entry gates; no hardware, SSH, USB or private data."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import slot_blocks as b
import slot_blocks_entry as e
import slot_session as ss

IDENT = {'target': 'misc-blocks', 'original': ss.MISC_SHA, 'candidate': b.PROBE_SHA, 'da': 'd' * 64, 'host': 'h' * 64, 'tools': 't' * 64, 'unit': 'u' * 64}
ORDER = (4, 3, 2, 1)


def misc_original():
    m = bytearray(b'\xff' * b.MISC_SIZE)
    for off in ss.MISC_COPIES:
        m[off:off + 16] = ss.MISC_BEFORE
    return bytes(m)


class OrderTests(unittest.TestCase):
    def test_probe_is_fixed_select_puts_the_trusted_copy_last_restore_reuses_the_order(self):
        self.assertEqual(e.order_for('probe', None), (4, 3, 2, 1))
        self.assertEqual(e.order_for('select', 2), (4, 3, 1, 2))
        self.assertEqual(e.order_for('select', 1), (4, 3, 2, 1))
        self.assertEqual(e.order_for('select-restore', None, [4, 3, 1, 2]), (4, 3, 1, 2))
        for bad in (None, 0, 5):
            with self.assertRaises(ValueError):
                e.order_for('select', bad)
        for bad in (None, [1, 2], 'abc', [1, 1, 2, 3]):
            with self.assertRaises(ValueError):
                e.order_for('probe-restore', None, bad)

    def test_sequencing_table(self):
        flags = lambda t, m: [p[0] for p in e.PRIOR[(t, m)]]
        self.assertEqual(flags('sig-block', 'identical'), [])
        self.assertEqual(flags('misc-blocks', 'probe'), ['prior_sig_block'])
        self.assertEqual(sorted(flags('misc-blocks', 'select')), ['prior_probe_restore', 'prior_rootfs_a'])
        self.assertEqual((flags('misc-blocks', 'probe-restore'), flags('misc-blocks', 'select-restore')), (['resume'], ['resume']))
        self.assertTrue(all(p[2] for k, v in e.PRIOR.items() if not k[1].endswith('restore') for p in v))
        self.assertTrue(all(not p[2] for k, v in e.PRIOR.items() if k[1].endswith('restore') for p in v))


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.before = misc_original()
        self.after = b.probe_image(self.before)
        self.new = b.blocks(self.after)
        self.sha_of = lambda c: e.digest(self.new[c - 1])
        self.header = {'mode': 'write', 'target': 'misc', 'order': list(ORDER), 'before_sha': ss.MISC_SHA, 'after_sha': b.PROBE_SHA}
        self.n = 0

    def events(self, steps=4, ack=True, final='TARGET_AND_GUARDS_VERIFIED', copies=ORDER):
        ev = [self.header]
        for c in copies[:steps]:
            ev += [{'write_attempt': 'write', 'copy': c, 'sha256': self.sha_of(c)}, {'write_result': 'write', 'copy': c, 'acknowledged': ack}]
        return ev + [{'status': final}]

    def run_dir(self, events=None, status='VERIFIED', age=0, ident=IDENT, mode='probe', order=ORDER):
        self.n += 1
        run = (self.root / f'r{self.n}').resolve()
        (run / 'j').mkdir(parents=True)
        journal = run / 'j' / 'journal.jsonl'
        journal.write_text(''.join(json.dumps(x) + '\n' for x in (events or self.events())))
        (run / 'receipt.json').write_text(json.dumps({'schema': 3, 'run': str(run), 'target': 'misc-blocks', 'mode': mode, 'status': status,
                                                      'identity': ident, 'created': time.time() - age, 'order': list(order),
                                                      'journal': 'j/journal.jsonl', 'journal_hash': e.digest(journal.read_bytes())}))
        return run

    def load(self, run, verified=True, kind='probe', order=ORDER):
        return e.load_blocks_prior(run, IDENT, self.header, kind, order, self.sha_of, verified)

    def test_good_verified_run_is_accepted(self):
        self.load(self.run_dir())

    def test_each_failure_is_refused(self):
        cases = {
            'stale': dict(age=90000), 'unverified': dict(status='STOP_UNVERIFIED'),
            'other unit': dict(ident={**IDENT, 'unit': 'x' * 64}), 'other image': dict(ident={**IDENT, 'candidate': 'x' * 64}),
            'other tools': dict(ident={**IDENT, 'tools': 'x' * 64}), 'wrong mode': dict(mode='select'),
            'unacknowledged': dict(events=self.events(ack=False)), 'short': dict(events=self.events(steps=3)),
            'no clean end': dict(events=self.events(final='STOP_UNVERIFIED_NO_RETRY_OR_REBOOT')),
            'wrong order': dict(events=self.events(copies=(1, 2, 3, 4))),
        }
        for name, kw in cases.items():
            with self.assertRaises(ValueError, msg=name):
                self.load(self.run_dir(**kw))

    def test_resume_accepts_a_stopped_partial_run_once_and_never_an_empty_one(self):
        partial = self.run_dir(self.events(steps=2, final='STOP_UNVERIFIED_NO_RETRY_OR_REBOOT'), status='STOP_UNVERIFIED')
        self.load(partial, verified=False)
        (partial / 'restore-claim.json').write_text('{}')
        with self.assertRaises(ValueError):
            self.load(partial, verified=False)
        empty = self.run_dir(self.events(steps=0, final='STOP_UNVERIFIED_NO_RETRY_OR_REBOOT'), status='STOP_UNVERIFIED')
        with self.assertRaises(ValueError):
            self.load(empty, verified=False)

    def test_edited_journal_and_a_claimed_verified_prior_are_refused(self):
        run = self.run_dir()
        (run / 'j' / 'journal.jsonl').write_text('{}\n')
        with self.assertRaises(ValueError):
            self.load(run)
        run = self.run_dir()
        (run / 'restore-claim.json').write_text('{}')
        with self.assertRaises(ValueError):
            self.load(run)

    def test_phrase_names_image_order_rootfs_a_and_hazards(self):
        text = e.phrase('misc-blocks', 'select', ss.MISC_A_SHA, ' ORDER 4312 ROOTFS-A abcdef123456 BROM-ROUTE-PROVEN', True)
        self.assertEqual(text, 'WRITE select misc-blocks cd512c873dd4 ORDER 4312 ROOTFS-A abcdef123456 BROM-ROUTE-PROVEN SAME-DISK')


class RestoreEvidenceTests(JournalTests):
    def restore_events(self, writes=((2, True),), final_sha=ss.MISC_SHA, status='TARGET_AND_GUARDS_VERIFIED'):
        old = b.blocks(self.before)
        ev = [{'mode': 'restore', 'target': 'misc', 'order': [4, 3, 2, 1], 'before_sha': ss.MISC_SHA, 'after_sha': b.PROBE_SHA}]
        for c, ack in writes:
            ev += [{'write_attempt': 'restore', 'copy': c, 'sha256': e.digest(old[c - 1])}, {'write_result': 'restore', 'copy': c, 'acknowledged': ack}]
        return ev + [{'read': 'final', 'name': 'misc', 'acknowledged': True, 'length': b.MISC_SIZE, 'sha256': final_sha}, {'status': status}]

    def make(self, events, observed=2, status='VERIFIED', age=0, ident=IDENT):
        self.n += 1
        run = (self.root / f'p{self.n}').resolve()
        (run / 'j').mkdir(parents=True)
        journal = run / 'j' / 'journal.jsonl'
        journal.write_text(''.join(json.dumps(x) + '\n' for x in events))
        (run / 'receipt.json').write_text(json.dumps({'schema': 3, 'run': str(run), 'target': 'misc-blocks', 'mode': 'probe-restore', 'status': status,
                                                      'identity': ident, 'created': time.time() - age, 'order': [4, 3, 2, 1], 'observed_copy': observed,
                                                      'journal': 'j/journal.jsonl', 'journal_hash': e.digest(journal.read_bytes())}))
        return run

    def load_pr(self, run):
        old = b.blocks(self.before)
        header = {'mode': 'restore', 'target': 'misc', 'order': [4, 3, 2, 1], 'before_sha': ss.MISC_SHA, 'after_sha': b.PROBE_SHA}
        return e.load_restore_prior(run, IDENT, header, lambda c: e.digest(old[c - 1]))

    def test_a_clean_restore_with_or_without_writes_is_accepted_and_reports_the_observed_copy(self):
        self.assertEqual(self.load_pr(self.make(self.restore_events()))['observed_copy'], 2)
        self.assertEqual(self.load_pr(self.make(self.restore_events(writes=())))['observed_copy'], 2)
        self.assertEqual(self.load_pr(self.make(self.restore_events(writes=((3, True), (1, True)))))['observed_copy'], 2)

    def test_bad_restore_evidence_is_refused(self):
        cases = {
            'unacknowledged': dict(events=self.restore_events(writes=((2, False),))),
            'not original': dict(events=self.restore_events(final_sha='x' * 64)),
            'no clean end': dict(events=self.restore_events(status='STOP_UNVERIFIED_NO_RETRY_OR_REBOOT')),
            'no observed copy': dict(events=self.restore_events(), observed=0),
            'stale': dict(events=self.restore_events(), age=90000),
            'unverified': dict(events=self.restore_events(), status='STOP_UNVERIFIED'),
            'other unit': dict(events=self.restore_events(), ident={**IDENT, 'unit': 'x' * 64}),
            'duplicate copy': dict(events=self.restore_events(writes=((2, True), (2, True)))),
        }
        for name, kw in cases.items():
            with self.assertRaises(ValueError, msg=name):
                self.load_pr(self.make(**kw))

    def test_a_restore_that_wrote_the_wrong_bytes_is_refused(self):
        ev = self.restore_events()
        ev[1]['sha256'] = 'x' * 64
        with self.assertRaises(ValueError):
            self.load_pr(self.make(ev))

    def test_a_claimed_restore_run_is_spent(self):
        run = self.make(self.restore_events())
        (run / 'restore-claim.json').write_text('{}')
        with self.assertRaises(ValueError):
            self.load_pr(run)


class GuardCrossCheckTests(unittest.TestCase):
    def table(self):
        return {'boot_a': {'offset': 0x11500000, 'size': 0x2000000, 'sha256': ss.BOOT_SHA}}

    def test_matching_guards_pass_and_typos_are_caught(self):
        e.check_guards(self.table(), (('boot_a', 0x11500000, 0x2000000, ss.BOOT_SHA),))
        for g in (('boot_a', 0x11500004, 0x2000000, ss.BOOT_SHA), ('boot_a', 0x11500000, 0x1000000, ss.BOOT_SHA),
                  ('boot_a', 0x11500000, 0x2000000, 'x' * 64), ('boot_x', 0x11500000, 0x2000000, ss.BOOT_SHA)):
            with self.assertRaises(ValueError):
                e.check_guards(self.table(), (g,))

    def test_sig_block_guards_are_checked_by_address(self):
        e.check_guards({}, (('rootfs_sig_a_b2', b.SIG_ADDR + 2 * b.BLOCK, b.BLOCK, 'a' * 64),))
        with self.assertRaises(ValueError):
            e.check_guards({}, (('rootfs_sig_a_b2', b.SIG_ADDR + 3 * b.BLOCK, b.BLOCK, 'a' * 64),))

    @unittest.skipUnless((Path(__file__).resolve().parents[2] / 'private/recovery/20261020-capture-prepared-20261021').exists(), 'private backup absent')
    def test_every_real_guard_matches_the_verified_backup(self):
        import common
        parts = {p['name']: p for p in common.backup_table(common.DEFAULT_BACKUP)}
        sig_a = Path(parts['rootfs_sig_a']['image']).read_bytes()
        for rootfs_a_ok in ((ss.ROOTFS_A_SHA,), ('a' * 64,)):
            e.check_guards(parts, b.misc_guards(rootfs_a_ok))
        for k in (1, 2, 3):
            e.check_guards(parts, b.sig_block_spec(sig_a, k)[0].guards)


class WaiverTests(unittest.TestCase):
    def test_waiver_drops_only_the_tools_hash(self):
        sig = bytes(range(256)) * 4096
        old = ss.ROOTFS_SIG
        try:
            ss.ROOTFS_SIG = e.digest(sig)
            spec, _ = b.sig_block_spec(sig, 1)
        finally:
            ss.ROOTFS_SIG = old
        base = {'da': 'd', 'host': 'h', 'tools': 't', 'unit': 'u'}
        strict, waived = e.sig_prior_expect(base, spec, False), e.sig_prior_expect(base, spec, True)
        self.assertIn('tools', strict)
        self.assertNotIn('tools', waived)
        self.assertEqual({k: v for k, v in strict.items() if k != 'tools'}, waived)
        for k in ('da', 'host', 'unit', 'original', 'candidate', 'rootfs_a', 'target'):
            self.assertIn(k, waived)


class SkipProbeTests(unittest.TestCase):
    def test_skip_probe_drops_only_the_probe_restore_prior_and_only_for_select(self):
        flags = lambda t, m, s: sorted(w[0] for w in e.wanted_priors(t, m, s))
        self.assertEqual(flags('misc-blocks', 'select', False), ['prior_probe_restore', 'prior_rootfs_a'])
        self.assertEqual(flags('misc-blocks', 'select', True), ['prior_rootfs_a'])
        for t, m in (('misc-blocks', 'probe'), ('misc-blocks', 'probe-restore'), ('misc-blocks', 'select-restore'), ('sig-block', 'identical')):
            with self.assertRaises(ValueError):
                e.wanted_priors(t, m, True)


class GateTests(unittest.TestCase):
    def run_main(self, *argv):
        with patch.object(sys, 'argv', ['slot_blocks_entry.py', *argv]):
            e.main()

    def test_bad_combinations_refuse_before_touching_data(self):
        for argv in (('sig-block', 'probe'), ('misc-blocks', 'identical'), ('misc-blocks', 'probe'), ('misc-blocks', 'select'),
                     ('misc-blocks', 'probe-restore'), ('sig-block', 'identical', '--block', '1', '--resume', '/x'),
                     ('misc-blocks', 'probe', '--prior-sig-block', '/x', '--block', '1'), ('sig-block', 'identical'),
                     ('misc-blocks', 'probe', '--prior-sig-block', '/x', '--resume', '/y'),
                     ('misc-blocks', 'probe-restore', '--resume', '/x'), ('misc-blocks', 'probe-restore', '--resume', '/x', '--observed-copy', '5'),
                     ('misc-blocks', 'probe', '--prior-sig-block', '/x', '--observed-copy', '2'),
                     ('misc-blocks', 'probe-restore', '--resume', '/x', '--observed-copy', '2', '--waive-sig-tools'),
                     ('sig-block', 'identical', '--block', '1', '--waive-sig-tools'),
                     ('misc-blocks', 'select', '--prior-probe-restore', '/x', '--prior-rootfs-a', '/y', '--last-copy', '1')):
            with self.assertRaises(ValueError, msg=argv):
                self.run_main(*argv)


if __name__ == '__main__':
    unittest.main()
