"""misc_entry: per-unit A selection (#327). Run: python3 tools/recovery/test_misc_entry.py"""
from pathlib import Path
import unittest

import misc_entry as m
import slot_session as s

FIRST = s.MISC_BEFORE                                          # the first unit's stock B-selected record
SECOND = bytes.fromhex('00414230ffffffff0e0001010f000101')    # the second unit's real record: both flags set


def misc_with(record):
    out = bytearray(b'\xff' * 0x100000)
    for off in s.MISC_COPIES:
        out[off:off + 16] = record
    return bytes(out)


class SelectionTests(unittest.TestCase):
    def test_first_unit_gets_exactly_the_old_constant(self):
        self.assertEqual(m.a_selected(FIRST), s.MISC_AFTER)

    def test_second_unit_keeps_its_b_flag_and_follows_the_vendor_recipe_for_a(self):
        self.assertEqual(m.a_selected(SECOND).hex(), '00414230ffffffff0f0300000e000101')

    def test_only_the_four_records_change_and_validate_agrees(self):
        for record in (FIRST, SECOND):
            original = misc_with(record)
            candidate = m.misc_candidate(original)
            changed = {i for i in range(len(original)) if original[i] != candidate[i]}
            self.assertTrue(all(any(o + 8 <= i < o + 13 for o in s.MISC_COPIES) for i in changed))
            m.validate_misc(original, candidate)
            with self.assertRaises(ValueError):
                m.validate_misc(original, original)

    def test_anything_but_a_stock_b_record_is_refused(self):
        for bad in (s.MISC_AFTER, bytes.fromhex('00414230ffffffff0e0001020f000100'), b'\xff' * 16, FIRST[:15]):
            with self.assertRaises(ValueError, msg=bad.hex()):
                m.a_selected(bad)
        with self.assertRaises(ValueError):
            m.misc_candidate(misc_with(s.MISC_AFTER))


class SpecTests(unittest.TestCase):
    def images(self, record):
        return {'misc': misc_with(record), 'rootfs_a': bytes(range(256)) * 0x40000,
                'rootfs_b': b'UBI#' + (bytes(range(256)) * 0x40000)[4:], 'boot_para': bytes(range(256)) * 0x2000}

    def test_spec_is_this_units_misc_and_candidate(self):
        images = self.images(SECOND)
        pins = s.unit_pins(images)
        spec = m.unit_misc_spec('c' * 64, pins, m.digest(m.misc_candidate(images['misc'])))
        self.assertEqual((spec.name, spec.addr, spec.size, spec.original_sha), ('misc', 0x700000, 0x100000, pins['misc']))
        guards = {g[0]: g[3] for g in spec.guards}
        self.assertEqual((guards['boot_para'], guards['rootfs_a']), (pins['boot_para'], 'c' * 64))
        self.assertEqual({g[0]: g[3] for g in spec.restore_guards}['rootfs_a'], ('c' * 64, pins['rootfs_a'], pins['rootfs_b']))
        self.assertEqual(guards['lk_a'], s.LK_A)  # the boot chain stays pinned

    def test_candidate_may_not_be_this_units_own_stock_image(self):
        pins = s.unit_pins(self.images(SECOND))
        for bad in (pins['rootfs_a'], pins['rootfs_b'], 'short'):
            with self.assertRaises(ValueError):
                m.unit_misc_spec(bad, pins, 'd' * 64)

    def test_default_first_unit_spec_is_unchanged(self):
        # slot_session.misc_spec still serves the first unit; this file does not replace it
        self.assertEqual(s.misc_spec('c' * 64).original_sha, s.MISC_SHA)


class PhraseTests(unittest.TestCase):
    def test_phrase_never_claims_the_route_is_proven_and_names_the_flag_change(self):
        for record, tail in ((FIRST, 'MISC-USB-ROUTE-UNPROVEN'), (SECOND, 'MISC-USB-ROUTE-UNPROVEN A-FLAG-01-TO-00')):
            original = misc_with(record)
            pins = s.unit_pins(SpecTests().images(record))
            spec = m.unit_misc_spec('c' * 64, pins, m.digest(m.misc_candidate(original)))
            text = m.phrase(spec, 'write', 'c' * 64, False, True, True, original)
            self.assertNotIn('BROM-ROUTE-PROVEN', text)
            self.assertTrue(text.endswith(f' ROOTFS-A cccccccccccc {tail} NO-SSH NO-UART'), text)


class FrozenToolsTests(unittest.TestCase):
    def test_this_file_is_not_hashed_into_receipts(self):
        # Receipts bind to the hash of these files; adding misc_entry to it would invalidate every earlier receipt.
        source = (Path(__file__).parent / 'slot_entry.py').read_text()
        self.assertNotIn('misc_entry', source)
        self.assertNotIn('misc_entry', (Path(__file__).parent / 'slot_session.py').read_text())


if __name__ == '__main__':
    unittest.main()
