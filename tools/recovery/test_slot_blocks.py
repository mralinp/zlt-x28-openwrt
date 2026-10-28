#!/usr/bin/env python3
"""Fake-DA tests only: never import USB or connect to a device."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import slot_blocks as b
import slot_session as ss

H = lambda d: hashlib.sha256(d).hexdigest()


def misc_original():
    m = bytearray(b'\xff' * b.MISC_SIZE)
    for off in ss.MISC_COPIES:
        m[off:off + 16] = ss.MISC_BEFORE
    return bytes(m)


class FakeDA:
    def __init__(self, misc):
        self.mem = {b.MISC_ADDR: bytearray(misc), 0x100: bytearray(b'G' * 16), 0x200: bytearray(b'H' * 16)}
        self.writes = []
        self.fail_write_at = self.drift_after = self.exception_at = None
        self.reads = 0

    def readflash(self, addr, length, filename, **kw):
        self.reads += 1
        for base, data in self.mem.items():
            if base <= addr < base + len(data):
                Path(filename).write_bytes(bytes(data[addr - base:addr - base + length]))
                return True
        raise KeyError(hex(addr))

    def writeflash(self, addr, length, filename, **kw):
        n = len(self.writes)
        self.writes.append((addr, length))
        if self.exception_at == n:
            raise OSError('lost USB')
        data = Path(filename).read_bytes()
        base = self.mem[b.MISC_ADDR]
        base[addr - b.MISC_ADDR:addr - b.MISC_ADDR + length] = data
        if self.drift_after == n:
            self.mem[0x100][:] = b'X' * 16
        return self.fail_write_at != n


GUARDS = (('g1', 0x100, 16, H(b'G' * 16)), ('g2', 0x200, 16, (H(b'H' * 16), H(b'I' * 16))))


class BlockwiseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.before = misc_original()
        self.probe = b.probe_image(self.before)
        self.select = b.select_image(self.before)

    def run_(self, da, mode='write', after=None, order=(4, 3, 2, 1)):
        after = after or self.probe
        return b.run_blockwise(da, self.before, after, H(after), order, self.out, mode=mode, guards=GUARDS)

    def journal(self):
        return [json.loads(l) for p in self.out.glob('*/journal.jsonl') for l in p.read_text().splitlines()]

    def test_images_are_exact_and_pinned(self):
        diff = [i for i, (x, y) in enumerate(zip(self.before, self.probe)) if x != y]
        self.assertEqual(diff, [off + 8 for off in ss.MISC_COPIES])
        self.assertEqual([self.probe[off + 8] for off in ss.MISC_COPIES], [0x0d, 0x0c, 0x0b, 0x0a])
        self.assertTrue(all(self.probe[off + 12] == 0x0f for off in ss.MISC_COPIES))  # B priority untouched: still selects B
        self.assertEqual(len([i for i, (x, y) in enumerate(zip(self.before, self.select)) if x != y]), 16)
        with self.assertRaises(ValueError):
            b.probe_image(b'\xff' * b.MISC_SIZE)

    def test_write_runs_one_block_per_request_in_order_and_ends_on_the_pinned_image(self):
        da = FakeDA(self.before)
        self.run_(da)
        self.assertEqual(da.writes, [(b.MISC_ADDR + k * b.BLOCK, b.BLOCK) for k in (3, 2, 1, 0)])
        self.assertEqual(bytes(da.mem[b.MISC_ADDR]), self.probe)
        self.assertEqual(self.journal()[-1]['status'], 'TARGET_AND_GUARDS_VERIFIED')

    def test_state_between_steps_never_has_more_than_one_block_in_flight(self):
        da = FakeDA(self.before)
        seen = []
        real = da.writeflash
        def spy(addr, length, filename, **kw):
            blocks = b.blocks(bytes(da.mem[b.MISC_ADDR]))
            seen.append(sum(1 for i in range(4) if blocks[i] != b.blocks(self.before)[i] and blocks[i] != b.blocks(self.probe)[i]))
            return real(addr, length, filename, **kw)
        da.writeflash = spy
        self.run_(da)
        self.assertEqual(seen, [0, 0, 0, 0])

    def test_restore_returns_to_the_original_from_any_mixed_state(self):
        for done in ((), (4,), (4, 3), (4, 3, 2, 1)):
            da = FakeDA(self.before)
            for c in done:
                da.mem[b.MISC_ADDR][(c - 1) * b.BLOCK:c * b.BLOCK] = b.blocks(self.probe)[c - 1]
            self.run_(da, 'restore', order=(1, 2, 3, 4))
            self.assertEqual(bytes(da.mem[b.MISC_ADDR]), self.before, done)

    def test_restore_tolerates_a_blank_or_half_written_target_but_not_foreign_other_blocks(self):
        da = FakeDA(self.before)
        da.mem[b.MISC_ADDR][0:b.BLOCK] = b'\xff' * b.BLOCK  # copy 1 blank
        da.mem[b.MISC_ADDR][b.BLOCK:2 * b.BLOCK] = b'\xff' * b.BLOCK  # copy 2 blank too
        with self.assertRaises(ValueError):
            self.run_(da, 'restore', order=(1, 2, 3, 4))  # block 2 is foreign while block 1 is being restored
        self.assertEqual(da.writes, [])

    def test_stops_without_retry_on_each_failure(self):
        for attr, at in (('fail_write_at', 1), ('drift_after', 1), ('exception_at', 2)):
            da = FakeDA(self.before)
            setattr(da, attr, at)
            with self.assertRaises((ValueError, OSError), msg=attr):
                self.run_(da)
            self.assertLessEqual(len(da.writes), at + 1, attr)
            self.assertEqual(self.journal()[-1]['status'], 'STOP_UNVERIFIED_NO_RETRY_OR_REBOOT')
            for p in self.out.glob('*'):
                import shutil
                shutil.rmtree(p)

    def test_bad_inputs_refused_before_any_io(self):
        da = FakeDA(self.before)
        for kw in (dict(order=(1, 2, 3)), dict(order=(1, 1, 2, 3)), dict(after=b'\x00' * b.MISC_SIZE)):
            with self.assertRaises(ValueError):
                self.run_(da, **kw)
        with self.assertRaises(ValueError):
            b.run_blockwise(da, self.before, self.probe, H(self.probe), (4, 3, 2, 1), self.out, mode='erase', guards=GUARDS)
        with self.assertRaises(ValueError):  # an image that is neither the pinned selection nor the probe
            other = bytearray(self.probe)
            other[0x900] = 0
            b.run_blockwise(da, self.before, bytes(other), H(bytes(other)), (4, 3, 2, 1), self.out, mode='write', guards=GUARDS)
        self.assertEqual((da.writes, da.reads), ([], 0))

    def test_selection_image_is_accepted_for_the_real_write(self):
        da = FakeDA(self.before)
        self.run_(da, after=self.select)
        self.assertEqual(bytes(da.mem[b.MISC_ADDR]), self.select)
        self.assertEqual((H(self.select), H(self.probe)), (ss.MISC_A_SHA, b.PROBE_SHA))


class SigBlockTests(unittest.TestCase):
    def test_block_spec_guards_the_other_blocks_and_refuses_the_certificate_block(self):
        sig = bytes(range(256)) * 4096
        with self.assertRaises(ValueError):
            b.sig_block_spec(sig, 1)  # not the real partition hash
        real = ss.ROOTFS_SIG
        orig = ss.ROOTFS_SIG
        try:
            ss.ROOTFS_SIG = H(sig)
            for k in (0, 4):
                with self.assertRaises(ValueError):
                    b.sig_block_spec(sig, k)
            spec, block = b.sig_block_spec(sig, 1)
        finally:
            ss.ROOTFS_SIG = orig
        self.assertEqual((spec.addr, spec.size, len(block)), (b.SIG_ADDR + b.BLOCK, b.BLOCK, b.BLOCK))
        names = {g[0] for g in spec.guards}
        self.assertTrue({'rootfs_sig_a_b0', 'rootfs_sig_a_b2', 'rootfs_sig_a_b3', 'misc', 'rootfs_a'} <= names)
        self.assertNotIn('rootfs_sig_a_b1', names)
        self.assertNotIn('rootfs_sig_a', names)
        self.assertEqual(spec.candidate_sha, spec.original_sha)


if __name__ == '__main__':
    unittest.main()
