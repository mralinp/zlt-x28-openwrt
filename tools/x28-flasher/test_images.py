"""Release download and local build commands (#285). Run: python3 tools/x28-flasher/test_images.py"""
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

import images


def release(bin_=b"\xffimage", sums_ok=True, extra=()):
    manifest = json.dumps({"padded_sha256": images.sha256(bin_)}).encode()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in (("manifest.json", manifest), ("rootfs-a-experimental.bin", bin_), *extra):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    blob = buf.getvalue()
    sums = f"{images.sha256(blob) if sums_ok else '0' * 64}  {images.ARCHIVE}\n".encode()
    listing = [{"tag_name": "v0.47.0", "assets": [{"name": images.ARCHIVE, "browser_download_url": "u/a"}, {"name": images.SUMS, "browser_download_url": "u/s"}]},
               {"tag_name": "v0.46.0", "assets": []}]
    files = {"u/a": blob, "u/s": sums}
    return lambda url: json.dumps(listing).encode() if "api.github" in url else files[url]


class DownloadTests(unittest.TestCase):
    def test_download_verifies_and_unpacks(self):
        root = Path(tempfile.mkdtemp())
        out = images.download(root, fetch=release())
        self.assertEqual(out.name, "native-ubi-release-v0.47.0")
        self.assertEqual((out / "rootfs-a-experimental.bin").read_bytes(), b"\xffimage")

    def test_checksum_mismatch_writes_nothing(self):
        root = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError):
            images.download(root, fetch=release(sums_ok=False))
        self.assertEqual(list(root.iterdir()), [])

    def test_manifest_must_match_image(self):
        fetch = release()
        listing = json.loads(fetch("https://api.github.com/x"))
        bad = release(bin_=b"a")
        blob = bad("u/a")
        with tarfile.open(fileobj=io.BytesIO(blob)) as src, tarfile.open(fileobj=(buf := io.BytesIO()), mode="w:gz") as dst:
            for name, data in (("manifest.json", b'{"padded_sha256": "x"}'), ("rootfs-a-experimental.bin", b"a")):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                dst.addfile(info, io.BytesIO(data))
        files = {"u/a": buf.getvalue(), "u/s": f"{images.sha256(buf.getvalue())}  {images.ARCHIVE}".encode()}
        with self.assertRaises(ValueError):
            images.download(Path(tempfile.mkdtemp()), fetch=lambda u: json.dumps(listing).encode() if "api.github" in u else files[u])

    def test_no_release_with_an_image(self):
        with self.assertRaises(RuntimeError):
            images.download(Path(tempfile.mkdtemp()), fetch=lambda u: b'[{"tag_name": "v1", "assets": []}]')


class LocalTests(unittest.TestCase):
    def test_commands_run_in_pipeline_order_and_chain_outputs(self):
        inputs = {"stock": "s.tgz", "modern": "m.tgz", "key": "k.pub", "kmods": "km", "extra_ipks": ["a.ipk"], "feed": ["f.ipk"]}
        work, out = Path("/w"), Path("/b/native-ubi-local-1")
        cmds = images.local_commands(inputs, work, out, Path("/r"))
        self.assertEqual([c[1].split("/")[-1] if c[0] == "python3" else c[1] for c in cmds], ["stage_native.py", "first_boot.py", "build", "run"])
        self.assertEqual(cmds[0][-1], "/w/stage")
        self.assertIn("/w/stage", cmds[1])
        self.assertIn("/w/profile:/profile:ro", cmds[3])
        self.assertEqual(cmds[3][-1], "/out/native-ubi-local-1")


if __name__ == "__main__":
    unittest.main()
