import pathlib
import tempfile
import unittest

import kmod_stub_feed as feed
import release_check as rc


def index(entries):
    return {n: {'Filename': f, 'SHA256sum': h} for n, f, h in entries}


class Compare(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp())

    def put(self, name, data=b'x'):
        (self.d / name).write_bytes(data)
        return rc.sha(self.d / name)

    def test_same_bytes_pass_and_foreign_packages_are_ignored(self):
        h = self.put('x28-leds_1_all.ipk')
        idx = index([('x28-leds', 'x28-leds_1_all.ipk', h), ('kmod-stub', 'kmod-stub_1_all.ipk', 'z')])
        self.assertEqual(rc.compare(idx, self.d), [])

    def test_same_name_different_bytes_is_flagged(self):
        self.put('x28-leds_1_all.ipk')
        idx = index([('x28-leds', 'x28-leds_1_all.ipk', 'other')])
        self.assertIn('bump the release number', rc.compare(idx, self.d)[0])

    def test_missing_either_way_is_flagged(self):
        self.put('x28-wifi_1_all.ipk')
        idx = index([('x28-leds', 'x28-leds_1_all.ipk', 'h')])
        self.assertEqual(len(rc.compare(idx, self.d)), 2)

    def test_pins(self):
        h = self.put('a.ipk')
        pins = self.d / 'pins'
        pins.write_text(f'{h}  a.ipk\n{h}  b.ipk\n')
        self.assertEqual(rc.check_pins(self.d, pins), ['missing b.ipk'])
        (self.d / 'a.ipk').write_bytes(b'y')
        self.assertEqual(rc.check_pins(self.d, pins)[0], 'differs from the pin: a.ipk')

    def test_committed_pins_name_every_sdk_built_package(self):
        names = {l.split()[1].split('_')[0] for l in rc.PINS.read_text().splitlines()}
        self.assertEqual(names, set(rc.sdk_built()))


if __name__ == '__main__':
    unittest.main()
