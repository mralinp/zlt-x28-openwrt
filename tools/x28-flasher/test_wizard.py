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
        fl.default_backup_dir = lambda: fl.PRIVATE / "backups" / "x28-backup-new"
        da.write_bytes(b"x")
        cfg = wizard.Config(fl.PRIVATE / "c.json")
        cfg.set("loader", str(da))
        ui = types.SimpleNamespace(text=lambda msg, default="": default, confirm=lambda msg, default=True: False)
        self.assertEqual(wizard.backup(fl, ui, cfg), 0)
        self.assertEqual(ran, ["countdown", ("usb_backup.py", ["--out", str(fl.PRIVATE / "backups" / "x28-backup-new"), "--loader", str(da), "--no-verify"])])

    def test_an_unfinished_backup_is_offered_for_resume(self):
        ran = []
        fl = types.SimpleNamespace(PRIVATE=Path(tempfile.mkdtemp()), power_off_countdown=lambda: None, run_tool=lambda s, a: ran.append(a) or 0)
        old = fl.PRIVATE / "backups" / "x28-backup-old"
        old.mkdir(parents=True)
        (old / "SHA256SUMS.partial").write_text("aa  images/a\nbb  images/b\n")
        fl.default_backup_dir = lambda: fl.PRIVATE / "backups" / "x28-backup-new"
        da = fl.PRIVATE / "DA.bin"
        da.write_bytes(b"x")
        cfg = wizard.Config(fl.PRIVATE / "c.json")
        cfg.set("loader", str(da))
        ui = types.SimpleNamespace(text=lambda msg, default="": str(default), confirm=lambda msg, default=True: True)
        wizard.backup(fl, ui, cfg)
        self.assertEqual(ran[0][1], str(old))


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

    def test_autopilot_stops_at_the_first_failed_step_and_flashes_nothing(self):
        import io
        from contextlib import redirect_stdout
        ran = []
        ui = types.SimpleNamespace(confirm=lambda *a, **k: False)
        with redirect_stdout(io.StringIO()), mock.patch.object(wizard, "backup", lambda *a: ran.append("backup") or 3), \
                mock.patch.object(wizard, "build", lambda *a: ran.append("build") or 0), mock.patch.object(wizard, "flash", lambda *a, **k: ran.append("flash") or 0):
            code = wizard.autopilot(types.SimpleNamespace(FROZEN=False), ui, None)
        self.assertEqual((code, ran), (3, ["backup"]))

    def test_autopilot_does_not_flash_from_a_frozen_binary(self):
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()), mock.patch.object(wizard, "backup", side_effect=AssertionError):
            self.assertEqual(wizard.autopilot(types.SimpleNamespace(FROZEN=True), None, None), 0)

    def test_build_reports_a_missing_release_without_crashing(self):
        import io
        from contextlib import redirect_stdout
        ui = types.SimpleNamespace(select=lambda msg, choices: "download")
        out = io.StringIO()
        with redirect_stdout(out), mock.patch("images.get", return_value=b"[]"):
            self.assertEqual(wizard.build(types.SimpleNamespace(FROZEN=False), ui, None), 1)
        self.assertIn("#254", out.getvalue())


if __name__ == "__main__":
    unittest.main()
