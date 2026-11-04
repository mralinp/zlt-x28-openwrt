"""Wizard helpers and the plain-prompt fallback (#272). Run: python3 tools/x28-flasher/test_wizard.py"""
import json
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "recovery"))  # the wizard imports common lazily, as x28_flasher arranges
import wizard  # noqa: E402


def receipt(root, name, status="VERIFIED", age=60):
    d = root / name
    d.mkdir(parents=True)
    (d / "receipt.json").write_text(json.dumps({"status": status, "created": time.time() - age}))
    return d


class HelperTests(unittest.TestCase):
    def test_only_fresh_verified_rehearsals_are_offered(self):
        root = Path(tempfile.mkdtemp())
        good = receipt(root, "slot-rootfs_a-identical-aaa")
        receipt(root, "slot-rootfs_a-identical-old", age=90000)
        receipt(root, "slot-rootfs_a-identical-bad", status="STOP_UNVERIFIED")
        self.assertEqual(wizard.verified_identicals(root), [good])

    def test_image_dirs_need_the_flashable_file(self):
        root = Path(tempfile.mkdtemp())
        (root / "native-ubi-1").mkdir()
        (root / "native-ubi-2").mkdir()
        (root / "native-ubi-2" / "rootfs-a-experimental.bin").write_bytes(b"x")
        self.assertEqual([d.name for d in wizard.image_dirs(root)], ["native-ubi-2"])

    def test_config_remembers_answers(self):
        path = Path(tempfile.mkdtemp()) / "sub" / "c.json"
        wizard.Config(path).set("loader", "/x")
        self.assertEqual(wizard.Config(path).get("loader"), "/x")
        self.assertEqual(wizard.Config(path).get("missing", "d"), "d")


class UartTests(unittest.TestCase):
    def test_console_text_scores_high_and_noise_low(self):
        self.assertGreater(wizard.printable_share(b"[  705.8] <3>.(3)[1440:ccci_sys] system message\r\n"), 0.95)
        self.assertLess(wizard.printable_share(bytes(range(128, 256)) * 2), 0.1)
        self.assertEqual(wizard.printable_share(b""), 0.0)


class BackupTests(unittest.TestCase):
    def test_backup_collects_answers_and_runs_the_tool(self):
        ran = []
        fl = types.SimpleNamespace(PRIVATE=Path(tempfile.mkdtemp()), default_backup_dir=lambda: Path("/x/b"), power_off_countdown=lambda: ran.append("countdown"),
                                   run_tool=lambda script, argv: ran.append((script, argv)) or 0)
        da = Path(tempfile.mkdtemp()) / "DA.bin"
        da.write_bytes(b"x")
        cfg = wizard.Config(fl.PRIVATE / "c.json")
        cfg.set("loader", str(da))
        ui = types.SimpleNamespace(text=lambda msg, default="": default, confirm=lambda msg, default=True: False)
        self.assertEqual(wizard.backup(fl, ui, cfg), 0)
        self.assertEqual(ran, ["countdown", ("usb_backup.py", ["--out", "/x/b", "--loader", str(da), "--no-verify"])])


class PlainPromptTests(unittest.TestCase):
    ui = wizard.Ui(fancy=False)

    def test_select_by_number_and_default(self):
        with mock.patch("builtins.input", side_effect=["", "9", "2"]):
            self.assertEqual(self.ui.select("pick", [("A", 1), ("B", 2)]), 1)
            self.assertEqual(self.ui.select("pick", [("A", 1), ("B", 2)]), 2)

    def test_text_and_confirm_defaults(self):
        with mock.patch("builtins.input", side_effect=["", "n", ""]):
            self.assertEqual(self.ui.text("path", "dflt"), "dflt")
            self.assertFalse(self.ui.confirm("go?", True))
            self.assertTrue(self.ui.confirm("go?", True))

    def test_menu_loop_runs_an_action_then_quits(self):
        calls = []
        started, stopped = [], []
        fl = types.SimpleNamespace(PRIVATE=Path(tempfile.mkdtemp()), start_capture=lambda ui: started.append(1), stop_capture=lambda: stopped.append(1))
        with mock.patch.dict(wizard.ACTIONS, {"test": lambda *a: calls.append("test")}), mock.patch("builtins.input", side_effect=["", "4", "8"]):
            self.assertEqual(wizard.run(fl, self.ui), 0)
        self.assertEqual(calls, ["test"])
        self.assertEqual((started, stopped), ([1], [1]))  # logger starts with the session and stops when it ends

    def test_placeholder_entries_say_what_is_coming(self):
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(wizard.coming("build")(None, None, None), 0)
        self.assertIn("#285", out.getvalue())


if __name__ == "__main__":
    unittest.main()
