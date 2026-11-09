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
            self.assertEqual(files('kmod-r'), {'./lib/modules/x28/a.ko': b'module', './etc/x28-kmods.d/50-kmod-r': b'a\n'})
            self.assertEqual(files('kmod-only'), {})

    def test_a_package_loads_after_the_packages_of_ours_it_depends_on(self):
        with tempfile.TemporaryDirectory() as d:
            kmods, out = Path(d) / 'ko', Path(d) / 'out'
            kmods.mkdir()
            for m in ('x', 'y', 'z'):
                (kmods / f'{m}.ko').write_bytes(m.encode())
            real = [('kmod-q', ['y', 'z'], kmods, ['kmod-p']), ('kmod-p', ['x'], kmods, []), ('kmod-none', [], kmods, ['kmod-q']),
                    ('kmod-r', ['x'], kmods, ['kmod-q', 'kmod-stub'])]
            f.build(['kmod-stub'], out, real)
            index = f.parse_index((out / 'Packages').read_text())

            def listing(name):
                outer = tarfile.open(out / index[name]['Filename'], 'r:gz')
                data = tarfile.open(fileobj=io.BytesIO(outer.extractfile('./data.tar.gz').read()), mode='r:gz')
                return {m.name: data.extractfile(m).read() for m in data if m.isfile() and m.name.startswith('./etc/x28-kmods.d/')}
            self.assertEqual(listing('kmod-p'), {'./etc/x28-kmods.d/50-kmod-p': b'x\n'})
            self.assertEqual(listing('kmod-q'), {'./etc/x28-kmods.d/51-kmod-q': b'y\nz\n'})  # the module order inside a package is kept
            self.assertEqual(listing('kmod-r'), {'./etc/x28-kmods.d/52-kmod-r': b'x\n'})
            self.assertEqual(listing('kmod-none'), {})  # nothing to load, no list
            self.assertEqual(listing('kmod-stub'), {})

    def test_data_archives_carry_their_parent_directories(self):
        with tempfile.TemporaryDirectory() as d:
            kmods, out = Path(d) / 'ko', Path(d) / 'out'
            kmods.mkdir()
            (kmods / 'a.ko').write_bytes(b'a')
            f.build(['kmod-stub'], out, [('kmod-r', ['a'], kmods, [])])
            index = f.parse_index((out / 'Packages').read_text())
            outer = tarfile.open(out / index['kmod-r']['Filename'], 'r:gz')
            data = tarfile.open(fileobj=io.BytesIO(outer.extractfile('./data.tar.gz').read()), mode='r:gz')
            names = [(m.name, m.isdir()) for m in data]
            dirs = [n for n, is_dir in names if is_dir]
            self.assertEqual(dirs, ['./etc', './lib', './etc/x28-kmods.d', './lib/modules', './lib/modules/x28'])
            for n, is_dir in names:  # a directory comes before everything inside it
                for other, _ in names:
                    if other.startswith(n.rstrip('/') + '/'):
                        self.assertLess([x for x, _ in names].index(n), [x for x, _ in names].index(other))
            stub = tarfile.open(out / index['kmod-stub']['Filename'], 'r:gz')
            self.assertEqual(tarfile.open(fileobj=io.BytesIO(stub.extractfile('./data.tar.gz').read()), mode='r:gz').getnames(), [])

    def test_the_loader_is_a_package_that_enables_itself(self):
        with tempfile.TemporaryDirectory() as d:
            init, out = Path(d) / 'init', Path(d) / 'out'
            init.write_bytes(b'#!/bin/sh /etc/rc.common\nSTART=97\n')
            f.build([], out, [], init)
            index = f.parse_index((out / 'Packages').read_text())
            p = index['x28-kmods']
            self.assertEqual((p['Version'], p['Architecture'], p['Depends']), (f'{f.VERSION}-r{f.REV}', 'all', f'kernel (= {f.VERSION})'))
            outer = tarfile.open(out / p['Filename'], 'r:gz')
            data = tarfile.open(fileobj=io.BytesIO(outer.extractfile('./data.tar.gz').read()), mode='r:gz')
            member = data.getmember('./etc/init.d/x28-kmods')
            self.assertEqual(member.mode, 0o755)
            self.assertEqual(data.extractfile(member).read(), init.read_bytes())
            ctrl = tarfile.open(fileobj=io.BytesIO(outer.extractfile('./control.tar.gz').read()), mode='r:gz')
            self.assertEqual({m.name: m.mode for m in ctrl}, {'./control': 0o644, './postinst': 0o755, './prerm': 0o755})
            self.assertIn(b'x28-kmods enable', ctrl.extractfile('./postinst').read())
            self.assertIn(b'x28-kmods disable', ctrl.extractfile('./prerm').read())
            self.assertIn(b'IPKG_INSTROOT', ctrl.extractfile('./postinst').read())  # an image build enables it itself
            self.assertNotIn('x28-kmods', index.keys() - {'x28-kmods'})

    def test_x28_packages_come_from_the_spec_with_modes_versions_and_enable_scripts(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'x').mkdir()
            (root / 'x/svc.init').write_text('START=50\n')
            (root / 'x/tool').write_text('#!/bin/sh\n')
            (root / 'x/data').write_text('d\n')
            spec = root / 'spec.ini'
            spec.write_text('[x28-svc]\nversion = 1.2.3\nrelease = 4\ndepends = netifd jshn\ndescription = A service\n  on two lines\n'
                            'files =\n    0755 /etc/init.d/x28-svc x/svc.init\n    0755 /sbin/x28-tool x/tool\n'
                            '[x28-plain]\nversion = 0.1.0\nrelease = 1\ndescription = Data\nfiles =\n    0644 /usr/share/x28/data x/data\n')
            pk = {p[0]: p for p in f.read_packages(spec)}
            name, depends, description, files, arch, scripts, version = pk['x28-svc']
            self.assertEqual((depends, description, arch, version), ('netifd, jshn', 'A service on two lines', 'all', '1.2.3-4'))
            self.assertEqual([(n, m) for n, _, m in files], [('./etc/init.d/x28-svc', 0o755), ('./sbin/x28-tool', 0o755)])
            self.assertEqual([n for n, _ in scripts], ['postinst', 'prerm'])
            self.assertIn(b'/etc/init.d/x28-svc enable', scripts[0][1])
            self.assertIn(b'/etc/init.d/x28-svc disable', scripts[1][1])
            self.assertIn(b'IPKG_INSTROOT', scripts[0][1])  # an image build enables it itself
            self.assertNotIn(b'x28-tool', scripts[0][1])
            self.assertEqual(pk['x28-plain'][5], [])  # no init script, no scripts
            out = Path(d) / 'out'
            f.build([], out, [], None, list(pk.values()))
            index = f.parse_index((out / 'Packages').read_text())
            self.assertEqual((index['x28-svc']['Version'], index['x28-svc']['Architecture'], index['x28-svc']['Depends']), ('1.2.3-4', 'all', 'netifd, jshn'))
            self.assertEqual(index['x28-svc']['Filename'], 'x28-svc_1.2.3-4_all.ipk')
            outer = tarfile.open(out / 'x28-svc_1.2.3-4_all.ipk', 'r:gz')
            data = tarfile.open(fileobj=io.BytesIO(outer.extractfile('./data.tar.gz').read()), mode='r:gz')
            self.assertEqual(data.getmember('./etc/init.d/x28-svc').mode, 0o755)
            self.assertTrue(data.getmember('./sbin').isdir() and data.getmember('./etc/init.d').isdir())  # parent directories

    def test_the_real_spec_builds_and_every_init_script_has_its_start_line(self):
        for name, depends, description, files, arch, scripts, version in f.read_packages():
            self.assertRegex(version, r'^\d+\.\d+\.\d+-\d+$', name)
            self.assertTrue(description and '\n' not in description, name)
            for dest, data, mode in files:
                self.assertIn(mode, (0o644, 0o755), dest)
                if dest.startswith('./etc/init.d/'):
                    self.assertRegex(data.decode(), r'(?m)^START=\d+$', dest)  # `enable` needs it
                    self.assertEqual(mode, 0o755, dest)
            if any(s[0] in ('postinst', 'prerm') for s in scripts):  # the enable and disable scripts exist for init scripts only
                self.assertTrue(any(d.startswith('./etc/init.d/') for d, _, _ in files), name)

    def test_a_config_file_is_listed_in_conffiles_and_a_package_may_have_no_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'cfg').write_text('option a 1\n')
            spec = root / 'spec.ini'
            spec.write_text('[x28-cfg]\nversion = 0.1.0\nrelease = 1\ndescription = Config\nfiles =\n    0644 /etc/config/x28 cfg conf\n'
                            '[x28-meta]\nversion = 0.1.0\nrelease = 1\ndepends = x28-cfg\ndescription = Meta\n')
            pk = {p[0]: p for p in f.read_packages(spec)}
            self.assertEqual([(s[0], s[1], s[2]) for s in pk['x28-cfg'][5]], [('conffiles', b'/etc/config/x28\n', 0o644)])
            self.assertEqual((pk['x28-meta'][3], pk['x28-meta'][5], pk['x28-meta'][1]), ([], [], 'x28-cfg'))
            out = Path(d) / 'out'
            f.build([], out, [], None, list(pk.values()))
            outer = tarfile.open(out / 'x28-cfg_0.1.0-1_all.ipk', 'r:gz')
            ctrl = tarfile.open(fileobj=io.BytesIO(outer.extractfile('./control.tar.gz').read()), mode='r:gz')
            self.assertEqual({m.name: m.mode for m in ctrl}, {'./control': 0o644, './conffiles': 0o644})
            self.assertEqual(f.parse_index((out / 'Packages').read_text())['x28-meta']['Depends'], 'x28-cfg')

    def test_x28_base_requires_every_other_package_of_the_spec(self):
        pk = {p[0]: p for p in f.read_packages()}
        base = set(pk['x28-base'][1].split(', '))
        others = set(pk) - {'x28-base'}
        self.assertEqual(others - base, set(), 'a package of the spec is not protected by x28-base')
        self.assertEqual(base - others, {'kernel', 'x28-kmods', 'x28-nrband'})  # the kernel record, the loader and the band tool, which are built elsewhere
        # nothing depends on x28-base, or removing it would be refused
        self.assertFalse([n for n, p in pk.items() if 'x28-base' in p[1].split(', ')])

    def test_nrband_is_an_aarch64_package_with_one_executable(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d) / 'x28-nrband'
            b.write_bytes(b'\x7fELF')
            name, depends, _, files, arch, scripts, version = f.nrband_package(b)
            self.assertEqual((name, depends, arch, scripts, version), ('x28-nrband', '', 'aarch64_generic', (), '0.1.0-2'))
            self.assertEqual(files, [('./usr/sbin/x28-nrband', b'\x7fELF', 0o755)])

    def test_epoch_keeps_the_stub_above_the_feed(self):
        self.assertTrue(f.VERSION.startswith('1:'))


if __name__ == '__main__':
    unittest.main()
