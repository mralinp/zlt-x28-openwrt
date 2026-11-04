"""usb_backup: resume, double-read check, and a result the guarded tools can load (#284)."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import common
import usb_backup

SMALL = 'dev:    size   erasesize  name\nmtd0: 00000040 00040000 "alpha"\nmtd1: 00000020 00040000 "beta"\n'


def fake_read(calls, flaky=None):
    def read(p, path):
        calls.append(p["name"])
        data = (p["name"].encode() * 64)[:p["size"]]
        if flaky and flaky == p["name"] and calls.count(p["name"]) == 2:
            data = b"x" * p["size"]  # second read disagrees
        Path(path).write_bytes(data)
        return True
    return read


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp())
        self.parts = common.parse_mtd(SMALL)

    def test_backup_is_loadable_by_the_guarded_tools_and_verified_by_two_reads(self):
        calls = []
        sums = usb_backup.write_backup(self.out, self.parts, fake_read(calls), say=lambda *_: None)
        self.assertEqual(calls, ["alpha", "alpha", "beta", "beta"])
        archive = usb_backup.seal(self.out, sums, SMALL)
        table = common.backup_table(self.out)
        self.assertEqual([p["name"] for p in table], ["alpha", "beta"])
        for p in table:
            self.assertEqual(common.sha256_file(p["image"]), p["sha256"])
        want = (self.out / "ARCHIVE.sha256").read_text().split()[0]
        self.assertEqual(want, hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertFalse((self.out / usb_backup.PARTIAL).exists())

    def test_disagreeing_reads_keep_nothing_for_that_partition(self):
        with self.assertRaisesRegex(RuntimeError, "disagree"):
            usb_backup.write_backup(self.out, self.parts, fake_read([], flaky="beta"), say=lambda *_: None)
        self.assertEqual((self.out / usb_backup.PARTIAL).read_text().count("\n"), 1)  # alpha is kept, beta is not

    def test_rerun_resumes_and_skips_finished_partitions(self):
        with self.assertRaises(RuntimeError):
            usb_backup.write_backup(self.out, self.parts, fake_read([], flaky="beta"), say=lambda *_: None)
        calls = []
        usb_backup.write_backup(self.out, self.parts, fake_read(calls), say=lambda *_: None)
        self.assertEqual(calls, ["beta", "beta"])

    def test_best_effort_partition_is_padded_noted_and_the_run_resumes_after_a_restart(self):
        parts = common.parse_mtd('dev:    size   erasesize  name\nmtd0: 00000040 00040000 "alpha"\nmtd1: 00000040 00040000 "expdb"\nmtd2: 00000040 00040000 "gamma"\n')

        def read(p, path):
            if p["name"] == "expdb":
                Path(path).write_bytes(b"e" * 0x10)  # only the first 16 of 64 bytes come back
                return False
            Path(path).write_bytes(p["name"].encode() * 64)
            Path(path).write_bytes(Path(path).read_bytes()[:p["size"]])
            return True
        with self.assertRaises(usb_backup.NeedsRestart):  # the agent is stuck after the fault: stop, keep what is done
            usb_backup.write_backup(self.out, parts, read, say=lambda *_: None)
        self.assertEqual((self.out / "images" / common.image_name(parts[1])).read_bytes(), b"e" * 0x10 + b"\xff" * 0x30)
        sums = usb_backup.write_backup(self.out, parts, read, say=lambda *_: None)  # after a power cycle: expdb is kept, gamma is read
        self.assertEqual(len(sums), 3)
        usb_backup.seal(self.out, sums, SMALL)
        self.assertIn("expdb: bytes 0x10..0x40 not read", (self.out / "BACKUP-NOTES.txt").read_text())
        with self.assertRaisesRegex(RuntimeError, "short"):  # alpha is not best-effort
            usb_backup.read_whole(lambda p, path: False, parts[0], self.out / "x.bin", usb_backup.BEST_EFFORT)

    def test_short_read_fails(self):
        def short(p, path):
            Path(path).write_bytes(b"x")
            return True
        with self.assertRaisesRegex(RuntimeError, "short"):
            usb_backup.write_backup(self.out, self.parts, short, say=lambda *_: None)

    def test_chunked_read_joins_pieces_and_names_the_failing_one(self):
        part = {"name": "big", "offset": 100, "size": 10}
        data = bytes(range(10))

        def readflash(addr, n, name):
            Path(name).write_bytes(data[addr - 100:addr - 100 + n])
            return True
        out = self.out / "big.bin"
        self.assertTrue(usb_backup.read_chunked(readflash, part, out, chunk=4, say=lambda *a, **k: None))
        self.assertEqual(out.read_bytes(), data)
        said = []

        def failing(addr, n, name):
            Path(name).write_bytes(data[:2])  # short piece
            return True
        self.assertFalse(usb_backup.read_chunked(failing, part, out, chunk=4, say=lambda m, **k: said.append(m)))
        self.assertIn("piece at +0x0", said[0])

    def test_bundled_layout_is_the_pinned_x28_layout(self):
        import restore_entry
        parts = common.parse_mtd(usb_backup.LAYOUT.read_text())
        layout = [{k: p[k] for k in ("index", "name", "size", "erase_size", "offset")} for p in parts]
        self.assertEqual(hashlib.sha256(json.dumps(layout, sort_keys=True).encode()).hexdigest(), restore_entry.LAYOUT_HASH)


if __name__ == "__main__":
    unittest.main()
