#!/usr/bin/env python3
"""The module list logic of package/x28-kmods/files/x28-kmods.init (#416): extracted and run with sh on temporary directories."""
import pathlib
import re
import subprocess
import tempfile
import unittest

INIT = pathlib.Path(__file__).resolve().parents[2] / 'package/x28-kmods/files/x28-kmods.init'
FUNC = re.search(r'^module_list\(\) \{\n.*?^\}\n', INIT.read_text(), re.M | re.S).group(0)


TRIES = re.search(r'^tries_reset\(\) \{\n.*?^\}\n', INIT.read_text(), re.M | re.S).group(0)


def tries(slot, a, b):
    """tries_reset against a fake cmdline, /proc/mtd and a file standing in for misc: A's byte is 2057, B's 2061, in all four copies."""
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        (d / 'cmdline').write_text(f'console=x bootslot={slot} y\n')
        (d / 'mtd').write_text('dev: size erasesize name\nmtd3: 00100000 00040000 "misc"\n')
        misc = bytearray(b'\xff' * 0x100000)
        for i in range(4):
            misc[2057 + 262144 * i] = a
            misc[2061 + 262144 * i] = b
        (d / 'mtd3').write_bytes(misc)
        fn = TRIES.replace('/proc/cmdline', str(d / 'cmdline')).replace('/proc/mtd', str(d / 'mtd')).replace('/dev/', str(d) + '/')
        return subprocess.run(['sh', '-c', fn + '\ntries_reset'], capture_output=True).returncode == 0


def run(mods, files):
    with tempfile.TemporaryDirectory() as d:
        listdir = pathlib.Path(d) / 'x28-kmods.d'
        if files is not None:
            listdir.mkdir()
            for name, text in files.items():
                (listdir / name).write_text(text)
        script = f"MODS='{mods}'\nLISTDIR='{listdir}'\n{FUNC}\nmodule_list\n"
        return subprocess.run(['sh', '-c', script], capture_output=True, text=True, check=True).stdout.split()


class TriesReset(unittest.TestCase):
    def test_each_slot_checks_its_own_byte(self):
        self.assertTrue(tries('a', 0, 5))
        self.assertFalse(tries('a', 1, 0))
        self.assertTrue(tries('b', 5, 0))
        self.assertFalse(tries('b', 0, 1))

    def test_no_slot_on_the_command_line_fails(self):
        self.assertFalse(tries('x', 0, 0))


class ModuleList(unittest.TestCase):
    def test_built_in_list_first_then_files_in_name_order(self):
        got = run('a b', {'51-late': 'e\nf\n', '50-early': 'c\nd\n'})
        self.assertEqual(got, ['a', 'b', 'c', 'd', 'e', 'f'])

    def test_a_module_listed_twice_loads_once(self):
        self.assertEqual(run('a b', {'50-x': 'b\nc\n', '51-y': 'c\na\nd\n'}), ['a', 'b', 'c', 'd'])

    def test_comments_blanks_and_spaces_are_ignored(self):
        self.assertEqual(run('a', {'50-x': '# the chacha libraries\n\n  b  \nc # trailing\n'}), ['a', 'b', 'c'])

    def test_no_list_directory_or_an_empty_one_leaves_the_built_in_list(self):
        self.assertEqual(run('a b', None), ['a', 'b'])
        self.assertEqual(run('a b', {}), ['a', 'b'])

    def test_dashes_are_kept_for_the_loader_to_map(self):
        self.assertEqual(run('a', {'50-x': 'usbip-core\ncdc-acm\n'}), ['a', 'usbip-core', 'cdc-acm'])


class Init(unittest.TestCase):
    def test_the_built_in_list_is_only_what_an_image_bakes(self):
        mods = re.search(r"^MODS='([^']*)'", INIT.read_text(), re.M).group(1).split()
        self.assertEqual(len(mods), 8)  # wireguard and the TPROXY/socket modules; everything else comes from list files
        self.assertLess(mods.index('x28_udp_lookup'), mods.index('nf_socket_ipv4'))
        self.assertLess(mods.index('nf_tproxy_ipv6'), mods.index('xt_TPROXY'))


if __name__ == '__main__':
    unittest.main()
