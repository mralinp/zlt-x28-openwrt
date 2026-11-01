import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import kmod_stub_feed as feed
import vendor_ipset as v


class VendorIpset(unittest.TestCase):
    def fixture(self, name='ipset'):
        control = ('Package: '+name+'\nVersion: 7.17-1\nArchitecture: aarch64_generic\n'
                   'Depends: libc, kmod-ipt-ipset, libmnl0, libipset13\nDescription: IPset utility\n\n')
        if name == 'libipset13':
            control = control.replace(', libipset13', '')
        return feed.tar_gz([('./debian-binary', b'2.0\n'),
                           ('./control.tar.gz', feed.tar_gz([('./control', control.encode()), ('./postinst', b'keep script')])),
                           ('./data.tar.gz', feed.tar_gz([('./usr/sbin/ipset', b'unchanged upstream payload')]))])

    def test_only_metadata_changes(self):
        original = self.fixture()
        with patch.object(v, 'UPSTREAM_SHA', hashlib.sha256(original).hexdigest()):
            control, output = v.repackage(original, v.REQUIRED_MODULES)
        self.assertIn('Version: 1:7.17-1-x28-1\n', control)
        self.assertIn('libc, x28-ipset-kernel (= '+feed.VERSION+'), libmnl0, libipset13 (= '+v.VERSION+')', control)
        self.assertNotIn('kmod-ipt-ipset', control)
        with tarfile.open(fileobj=io.BytesIO(original), mode='r:gz') as before, tarfile.open(fileobj=io.BytesIO(output), mode='r:gz') as after:
            self.assertEqual(before.extractfile('./data.tar.gz').read(), after.extractfile('./data.tar.gz').read())
            with tarfile.open(fileobj=io.BytesIO(before.extractfile('./control.tar.gz').read()), mode='r:gz') as bc, tarfile.open(fileobj=io.BytesIO(after.extractfile('./control.tar.gz').read()), mode='r:gz') as ac:
                self.assertEqual(bc.extractfile('./postinst').read(), ac.extractfile('./postinst').read())
                self.assertEqual(bc.getmember('./postinst').mode, ac.getmember('./postinst').mode)

    def test_unknown_input_rejected(self):
        with self.assertRaisesRegex(ValueError, 'upstream'):
            v.repackage(self.fixture(), v.REQUIRED_MODULES)

    def test_missing_observed_module_rejected(self):
        original = self.fixture()
        with patch.object(v, 'UPSTREAM_SHA', hashlib.sha256(original).hexdigest()), self.assertRaisesRegex(ValueError, 'ip_set_hash_net'):
            v.repackage(original, v.REQUIRED_MODULES - {'ip_set_hash_net'})

    def test_build_adds_explicit_subset_without_full_aggregate(self):
        original = self.fixture()
        library = self.fixture('libipset13')
        with tempfile.TemporaryDirectory() as d, patch.object(v, 'UPSTREAM_SHA', hashlib.sha256(original).hexdigest()), patch.object(v, 'LIBRARY_SHA', hashlib.sha256(library).hexdigest()):
            out = Path(d)/'feed'
            v.build(original, library, v.REQUIRED_MODULES, out)
            index = feed.parse_index((out/'Packages').read_text())
            self.assertEqual(set(index), {'kernel', 'x28-ipset-kernel', 'libipset13', 'ipset'})
            for entry in index.values():
                payload = (out/entry['Filename']).read_bytes()
                self.assertEqual(entry['SHA256sum'], hashlib.sha256(payload).hexdigest())
            self.assertIn('x28-ipset-kernel', index)
            self.assertNotIn('kmod-ipt-ipset', index)
            self.assertIn('hash:ip,mac', index['x28-ipset-kernel']['Description'])
            with self.assertRaises(FileExistsError):
                v.build(original, library, v.REQUIRED_MODULES, out)
            v.build(original, library, v.REQUIRED_MODULES, Path(d)/'stubs', ['kmod-tun'])
            self.assertEqual(feed.parse_index((Path(d)/'stubs/Packages').read_text())['kmod-tun']['Depends'], 'kernel (= '+feed.VERSION+')')


if __name__ == '__main__':
    unittest.main()
