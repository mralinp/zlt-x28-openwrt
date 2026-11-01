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
        (source/'Packages').write_bytes(b'index')
        (source/'Packages.gz').write_bytes(gzip.compress(b'index', compresslevel=1))
        (source/'one.ipk').write_bytes(b'reviewed package')
        (source/'secret.sec').write_bytes(b'never publish')
        public=root/'key.pub';public.write_bytes(b'public key')
        private=root/'key.sec';private.write_bytes(b'private key')
        hashes={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in ['Packages','one.ipk']}
        return source,private,public,hashes

    def test_only_reviewed_assets_and_public_key_are_staged(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,private,public,hashes=self.setup_files(root)
            def usign(args, **kwargs):
                if '-S' in args: Path(args[args.index('-x')+1]).write_bytes(b'signature')
                return subprocess.CompletedProcess(args,0)
            with patch.dict(f.INPUT_HASHES,hashes,clear=True),patch.object(f.subprocess,'run',side_effect=usign):
                f.prepare(source,private,public,root/'release')
            self.assertEqual({p.name for p in (root/'release').iterdir()},set(hashes)|{'Packages.gz','Packages.sig','x28-feed.pub','SHA256SUMS'})
            self.assertEqual(gzip.decompress((root/'release/Packages.gz').read_bytes()),b'index')
            self.assertNotIn(b'private key',b''.join(p.read_bytes() for p in (root/'release').iterdir()))
            self.assertNotIn(b'never publish',b''.join(p.read_bytes() for p in (root/'release').iterdir()))

    def test_changed_asset_refused_before_output_or_signing(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,private,public,hashes=self.setup_files(root)
            (source/'one.ipk').write_bytes(b'changed')
            with patch.dict(f.INPUT_HASHES,hashes,clear=True),patch.object(f.subprocess,'run') as run:
                with self.assertRaises(ValueError): f.prepare(source,private,public,root/'release')
                run.assert_not_called();self.assertFalse((root/'release').exists())

    def test_mismatched_key_leaves_no_publishable_output(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,private,public,hashes=self.setup_files(root)
            def mismatch(args, **kwargs):
                if '-S' in args:
                    Path(args[args.index('-x')+1]).write_bytes(b'signature')
                    return subprocess.CompletedProcess(args,0)
                raise subprocess.CalledProcessError(1,args)
            with patch.dict(f.INPUT_HASHES,hashes,clear=True),patch.object(f.subprocess,'run',side_effect=mismatch):
                with self.assertRaises(subprocess.CalledProcessError): f.prepare(source,private,public,root/'release')
                self.assertFalse((root/'release').exists())

    def test_compressed_index_must_match_reviewed_plaintext(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,private,public,hashes=self.setup_files(root)
            (source/'Packages.gz').write_bytes(gzip.compress(b'other index'))
            with patch.dict(f.INPUT_HASHES,hashes,clear=True),patch.object(f.subprocess,'run') as run:
                with self.assertRaises(ValueError): f.prepare(source,private,public,root/'release')
                run.assert_not_called();self.assertFalse((root/'release').exists())

    def test_existing_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,private,public,hashes=self.setup_files(root)
            out=root/'release';out.mkdir();(out/'keep').write_text('keep')
            with patch.dict(f.INPUT_HASHES,hashes,clear=True),self.assertRaises(FileExistsError): f.prepare(source,private,public,out)
            self.assertEqual((out/'keep').read_text(),'keep')


if __name__=='__main__':unittest.main()
