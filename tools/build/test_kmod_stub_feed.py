#!/usr/bin/env python3
import gzip
import hashlib
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
import kmod_stub_feed as f


def kmod(ko=(), depends=()):
    return {'ko': set(ko), 'depends': list(depends)}


class Covered(unittest.TestCase):
    def test_present_and_missing_modules(self):
        kmods = {'kmod-a': kmod(['a']), 'kmod-b': kmod(['b'])}
        self.assertEqual(f.covered(kmods, {'a'}), ['kmod-a'])

    def test_missing_dependency_excludes_the_user(self):
        kmods = {'kmod-a': kmod(['a'], ['kmod-b', 'libc']), 'kmod-b': kmod(['b'])}
        self.assertEqual(f.covered(kmods, {'a'}), [])

    def test_dependency_not_in_feed_excludes_the_user(self):
        self.assertEqual(f.covered({'kmod-a': kmod(['a'], ['kmod-gone'])}, {'a'}), [])

    def test_renamed_needs_every_replacement(self):
        kmods = {'kmod-log': kmod(['nf_log_syslog'])}
        self.assertEqual(f.covered(kmods, {'nf_log_common', 'nf_log_ipv4'}), [])
        self.assertEqual(f.covered(kmods, {'nf_log_common', 'nf_log_ipv4', 'nf_log_ipv6'}), ['kmod-log'])

    def test_partially_available_packages_and_dependents_are_refused(self):
        kmods = {'kmod-ipt-ipset': kmod(['ip_set', 'ip_set_hash_ipmac']),
                 'kmod-ipt-extra': kmod(['xt_cgroup']), 'kmod-inet-diag': kmod(['raw_diag']),
                 'kmod-dependent': kmod([], ['kmod-ipt-ipset'])}
        self.assertEqual(f.covered(kmods, {'ip_set'}), [])

    def test_named_dependency_can_be_skipped(self):
        kmods = {'kmod-crypto-arc4': kmod(['arc4'], ['kmod-crypto-user']), 'kmod-crypto-user': kmod(['af_alg']),
                 'kmod-mppe': kmod(['ppp_mppe'], ['kmod-crypto-arc4'])}
        self.assertEqual(f.covered(kmods, {'arc4', 'ppp_mppe'}), ['kmod-crypto-arc4', 'kmod-mppe'])

    def test_dependency_cycle_ends(self):
        kmods = {'kmod-a': kmod(['a'], ['kmod-b']), 'kmod-b': kmod(['b'], ['kmod-a'])}
        self.assertEqual(f.covered(kmods, {'a', 'b'}), ['kmod-a', 'kmod-b'])

    def test_dash_and_underscore_are_the_same_module(self):
        self.assertEqual(f.covered({'kmod-a': kmod(['mdio-gpio'])}, {f.norm('mdio-gpio')}), ['kmod-a'])


class Verify(unittest.TestCase):
    def test_builtin_needs_live_proof(self):
        kmods = {'kmod-a': kmod(['a', 'b', 'c', 'd', 'e'])}
        objects = {'b': {'CONFIG_B'}, 'c': {'CONFIG_C'}, 'd': {'CONFIG_D'}}
        config = {'CONFIG_B': 'y', 'CONFIG_C': 'm'}
        self.assertEqual(f.unproven(['kmod-a'], kmods, {'a'}, objects, config, {'e'}), ['c', 'd'])

    def test_objects_read_from_makefile(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'Makefile').write_text('obj-$(CONFIG_TUN) += tun.o \\\n  mdio-gpio.o\nfoo := bar.o\n')
            self.assertEqual(f.builtin_objects(d), {'tun': {'CONFIG_TUN'}, 'mdio_gpio': {'CONFIG_TUN'}})


class Build(unittest.TestCase):
    def test_index_matches_the_packages(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            self.assertEqual(f.build(['kmod-a'], out), 2)
            index = f.parse_index((out / 'Packages').read_text())
            self.assertEqual(gzip.decompress((out / 'Packages.gz').read_bytes()), (out / 'Packages').read_bytes())
            self.assertEqual(index['kmod-a']['Depends'], f'kernel (= {f.VERSION})')
            self.assertEqual(index['kmod-a']['Version'], f.VERSION)
            for p in index.values():
                data = (out / p['Filename']).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), p['SHA256sum'])
                self.assertEqual(len(data), int(p['Size']))
                self.assertNotIn(':', p['Filename'])

    def test_stub_installs_no_files(self):
        _, ipk = f.stub('kmod-a', '', 'x')
        outer = tarfile.open(fileobj=io.BytesIO(ipk), mode='r:gz')
        self.assertEqual(set(outer.getnames()), {'./debian-binary', './data.tar.gz', './control.tar.gz'})
        data = tarfile.open(fileobj=io.BytesIO(outer.extractfile('./data.tar.gz').read()), mode='r:gz')
        self.assertEqual(data.getnames(), [])

    def test_real_packages_carry_the_module_and_a_revision(self):
        with tempfile.TemporaryDirectory() as d:
            kmods, out, manifest = Path(d) / 'ko', Path(d) / 'out', Path(d) / 'real.txt'
            kmods.mkdir()
            (kmods / 'a.ko').write_bytes(b'module')
            manifest.write_text('# comment\nkmod-r a | kmod-a\nkmod-only | kmod-r\n')
            real = f.read_real(manifest, kmods)
            self.assertEqual(real, [('kmod-r', ['a'], kmods, ['kmod-a']), ('kmod-only', [], kmods, ['kmod-r'])])
            self.assertEqual(f.build(['kmod-a'], out, real), 4)
            index = f.parse_index((out / 'Packages').read_text())
            self.assertEqual(index['kmod-a']['Version'], f.VERSION)  # stubs keep the plain version
            for name in ('kmod-r', 'kmod-only'):
                self.assertEqual(index[name]['Version'], f'{f.VERSION}-r{f.REV}')
                self.assertTrue(index[name]['Depends'].startswith(f'kernel (= {f.VERSION})'))
                self.assertNotIn(':', index[name]['Filename'])
            self.assertEqual(index['kmod-r']['Depends'], f'kernel (= {f.VERSION}), kmod-a')

            def files(name):
                outer = tarfile.open(out / index[name]['Filename'], 'r:gz')
                data = tarfile.open(fileobj=io.BytesIO(outer.extractfile('./data.tar.gz').read()), mode='r:gz')
                return {m.name: data.extractfile(m).read() for m in data if m.isfile()}
            self.assertEqual(files('kmod-r'), {'./lib/modules/x28/a.ko': b'module'})
            self.assertEqual(files('kmod-only'), {})

    def test_epoch_keeps_the_stub_above_the_feed(self):
        self.assertTrue(f.VERSION.startswith('1:'))


if __name__ == '__main__':
    unittest.main()
