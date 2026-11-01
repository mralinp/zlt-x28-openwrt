import hashlib
import gzip
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
import feed_release as f


class FeedRelease(unittest.TestCase):
    def setup_files(self, root):
        source=root/'source';source.mkdir()
        package=b'reviewed package'
        index=b'Package: one\nFilename: one.ipk\nSHA256sum: '+hashlib.sha256(package).hexdigest().encode()+b'\n\n'
        (source/'Packages').write_bytes(index)
        (source/'Packages.gz').write_bytes(gzip.compress(index, compresslevel=1))
        (source/'one.ipk').write_bytes(package)
        (source/'secret.sec').write_bytes(b'never publish')
        public=root/'key.pub';public.write_bytes(b'public key')
        private=root/'key.sec';private.write_bytes(b'private key')
        return source,private,public,hashlib.sha256(index).hexdigest()

    def test_only_indexed_assets_and_public_key_are_staged(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,private,public,pin=self.setup_files(root)
            def usign(args, **kwargs):
                if '-S' in args: Path(args[args.index('-x')+1]).write_bytes(b'signature')
                return subprocess.CompletedProcess(args,0)
            with patch.object(f,'INDEX_SHA256',pin),patch.object(f.subprocess,'run',side_effect=usign):
                f.prepare(source,private,public,root/'release')
            self.assertEqual({p.name for p in (root/'release').iterdir()},{'Packages','one.ipk','Packages.gz','Packages.sig','x28-feed.pub','SHA256SUMS'})
            self.assertEqual(gzip.decompress((root/'release/Packages.gz').read_bytes()),(source/'Packages').read_bytes())
            self.assertNotIn(b'private key',b''.join(p.read_bytes() for p in (root/'release').iterdir()))
            self.assertNotIn(b'never publish',b''.join(p.read_bytes() for p in (root/'release').iterdir()))

    def refused(self, change):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,private,public,pin=self.setup_files(root)
            change(source)
            with patch.object(f,'INDEX_SHA256',pin),patch.object(f.subprocess,'run') as run:
                with self.assertRaises(ValueError): f.prepare(source,private,public,root/'release')
                run.assert_not_called();self.assertFalse((root/'release').exists())

    def test_changed_package_refused_before_signing(self):
        self.refused(lambda s:(s/'one.ipk').write_bytes(b'changed'))

    def test_changed_index_refused_before_signing(self):
        self.refused(lambda s:(s/'Packages').write_bytes(b'Package: other\n\n'))

    def test_compressed_index_must_match_reviewed_plaintext(self):
        self.refused(lambda s:(s/'Packages.gz').write_bytes(gzip.compress(b'other index')))

    def test_mismatched_key_leaves_no_publishable_output(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,private,public,pin=self.setup_files(root)
            def mismatch(args, **kwargs):
                if '-S' in args:
                    Path(args[args.index('-x')+1]).write_bytes(b'signature')
                    return subprocess.CompletedProcess(args,0)
                raise subprocess.CalledProcessError(1,args)
            with patch.object(f,'INDEX_SHA256',pin),patch.object(f.subprocess,'run',side_effect=mismatch):
                with self.assertRaises(subprocess.CalledProcessError): f.prepare(source,private,public,root/'release')
                self.assertFalse((root/'release').exists())

    def test_existing_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,private,public,pin=self.setup_files(root)
            out=root/'release';out.mkdir();(out/'keep').write_text('keep')
            with patch.object(f,'INDEX_SHA256',pin),self.assertRaises(FileExistsError): f.prepare(source,private,public,out)
            self.assertEqual((out/'keep').read_text(),'keep')


if __name__=='__main__':unittest.main()
