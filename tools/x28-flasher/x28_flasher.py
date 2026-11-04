#!/usr/bin/env python3
"""x28-flasher: guided front end for the ZLT X28 recovery tools (#272).

Picks the UART, keeps its capture running, then hands over to the guarded tools in tools/recovery/, which
keep every guard (dry run, receipts, typed phrase, second backup copy, base hash). Nothing here writes flash itself.

    x28_flasher.py                 menu
    x28_flasher.py ports           serial ports found
    x28_flasher.py uart            capture the chosen UART to a log (Ctrl-C stops)
    x28_flasher.py read [part]     read one partition by name and compare with the backup (read-only)
    x28_flasher.py flash identical|write --candidate-dir D [--base-dir D] [--prior-identical RUN]
"""
import argparse
import glob
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
RECOVERY = (Path(sys._MEIPASS) if FROZEN else Path(__file__).resolve().parents[1]) / "recovery"
sys.path.insert(0, str(RECOVERY))
from common import MTK_HOME, PRIVATE, VENDOR_DA, ensure_venv  # noqa: E402

VENV_PY = MTK_HOME / "venv" / "bin" / "python"
if "--selftest" not in sys.argv:
    ensure_venv()

BACKUP_NAME = "x28-backup/complete-captured-partitions.tar"
NOISE = ("debug-console", "Bluetooth")


def list_ports():
    from serial.tools import list_ports as lp
    return [(p.device, p.description) for p in lp.comports() if not any(n in p.device for n in NOISE)]


def pick(items, what, ask=input):
    """Numbered choice; returns the chosen item. Enter takes the only/first entry."""
    if not items:
        sys.exit(f"no {what} found")
    for i, item in enumerate(items, 1):
        print(f"  {i}) {item}")
    while True:
        answer = ask(f"{what} [1]: ").strip() or "1"
        if answer.isdigit() and 1 <= int(answer) <= len(items):
            return items[int(answer) - 1]
        print("  enter a number from the list")


def find_backup_copies():
    roots = ["/Volumes/*", "/media/*", "/media/*/*", "/run/media/*/*"]
    return sorted(p for r in roots for p in glob.glob(f"{r}/{BACKUP_NAME}"))


class Capture(threading.Thread):
    """Writes everything the UART sends to a log; the guarded tools demand it was updated within 60 s."""

    def __init__(self, port, baud, path):
        super().__init__(daemon=True)
        self.port, self.baud, self.path, self.stop_event, self.bytes = port, baud, path, threading.Event(), 0

    def run(self):
        import serial
        with serial.Serial(self.port, self.baud, timeout=0.5) as ser, open(self.path, "wb") as log:
            while not self.stop_event.is_set():
                data = ser.read(4096)
                if data:
                    log.write(data)
                    log.flush()
                    self.bytes += len(data)


def start_capture(ask=input):
    port = pick([d for d, _ in list_ports()], "UART port", ask)
    baud = int(ask("baud rate [921600]: ").strip() or 921600)  # the X28 console; 115200 is garbage
    path = PRIVATE / "usb-probe" / f"uart-{time.strftime('%Y%m%d-%H%M%S')}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    cap = Capture(port, baud, path)
    cap.start()
    time.sleep(3)
    print(f"capturing {port} @ {baud} -> {path} ({cap.bytes} bytes so far)")
    if not cap.bytes:
        print("  nothing received yet. A silent line is fine until the router boots, but the tools refuse a log\n"
              "  that was not updated within the last 60 s, so the baud rate must be right (the X28 console is 921600) and the router must be sending.")
    return cap, path


def flash_cmd(args, uart, backup_copy):
    cmd = ["rootfs_a", args.mode, "--write", *tool_paths(args),
           "--candidate-dir", args.candidate_dir, "--backup-copy", str(backup_copy), "--uart-log", str(uart)]
    for flag in ("base_dir", "prior_identical"):
        if getattr(args, flag):
            cmd += ["--" + flag.replace("_", "-"), getattr(args, flag)]
    return cmd


def run_tool(script, argv):
    """The guarded tools run in this process when frozen (no second interpreter), else under the mtkclient venv."""
    if FROZEN:
        import runpy
        sys.argv = [script, *argv]
        try:
            runpy.run_path(str(RECOVERY / script), run_name="__main__")
        except SystemExit as done:
            return done.code or 0
        return 0
    return subprocess.call([str(VENV_PY), str(RECOVERY / script), *argv])


def tool_paths(args):
    """--backup/--loader are explicit in a frozen binary: there is no repo with a private/ folder next to it."""
    out = []
    for flag in ("backup", "loader"):
        if getattr(args, flag, None):
            out += [f"--{flag}", getattr(args, flag)]
    if FROZEN and len(out) < 4:
        sys.exit("pass --backup DIR (your verified backup) and --loader FILE (the vendor download agent)")
    return out


def cmd_flash(args):
    if FROZEN:  # auditor gate (#272): lifted by the PR that asserts the compiled library and tool sources equal the bundled copies
        sys.exit("frozen builds are read-only until the build-time equality gate exists (#272); flash from a source checkout")
    loader = Path(args.loader) if args.loader else VENDOR_DA
    if not loader.is_file():
        sys.exit(f"download agent missing: {loader}")
    copies = find_backup_copies()
    copy = args.backup_copy or (pick(copies, "second backup copy") if copies else None)
    if not copy:
        sys.exit(f"no second backup copy found (looked for */{BACKUP_NAME}); pass --backup-copy")
    cap, uart = start_capture()
    print("\nNext: the tool shows the exact phrase to type (you type it yourself), then asks you to unplug the\n"
          "router for 10 s or more and plug it back in with no buttons. No retry, no automatic reboot.\n")
    try:
        sys.exit(run_tool("slot_entry.py", flash_cmd(args, uart, copy)))
    finally:
        cap.stop_event.set()
        print(f"UART log: {uart}")


def power_off_countdown(seconds=10, ask=input, sleep=time.sleep):
    """The preloader only answers for ~1 s after power-on and a stuck DA needs a full power-off first."""
    ask("Unplug the router's power, then press Enter: ")
    for left in range(seconds, 0, -1):
        print(f"\r  keep the power off: {left:2d} s ", end="", flush=True)
        sleep(1)
    print("\r  off long enough. Starting the tool now; plug the power in as soon as it says it is waiting (no buttons).")


def cmd_read(args):
    argv = [args.partition, *tool_paths(args)]  # before the countdown, so missing paths fail at once
    power_off_countdown()
    sys.exit(run_tool("read_by_name.py", argv))


def cmd_uart(args):
    cap, path = start_capture()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cap.stop_event.set()
        print(f"\nstopped, {cap.bytes} bytes in {path}")


def cmd_identity(args):
    """SHA-256 of the XML library the guards bind as 'host'; the build smoke test compares it with a developer install."""
    import hashlib
    from restore_entry import host_identity
    print(hashlib.sha256(host_identity().encode()).hexdigest())


def cmd_ports(args):
    for dev, desc in list_ports():
        print(f"{dev}  {desc}")


def selftest():
    answers = iter(["", "x", "2"])
    assert pick(["a", "b"], "thing", lambda _: next(answers)) == "a"
    assert pick(["a", "b"], "thing", lambda _: next(answers)) == "b"
    args = argparse.Namespace(mode="write", candidate_dir="C", base_dir="B", prior_identical="P", backup="Bk", loader="L")
    cmd = flash_cmd(args, Path("u.log"), Path("b.tar"))
    assert cmd[-4:] == ["--base-dir", "B", "--prior-identical", "P"] and "--write" in cmd and "rootfs_a" in cmd
    assert "--base-dir" not in flash_cmd(argparse.Namespace(mode="identical", candidate_dir="C", base_dir=None, prior_identical=None, backup="Bk", loader="L"),
                                         Path("u"), Path("b"))
    asked = []
    power_off_countdown(2, ask=asked.append, sleep=lambda _: None)
    assert len(asked) == 1
    print("selftest ok")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("ports").set_defaults(fn=cmd_ports)
    sub.add_parser("uart").set_defaults(fn=cmd_uart)
    sub.add_parser("identity").set_defaults(fn=cmd_identity)
    r = sub.add_parser("read")
    r.add_argument("partition", nargs="?", default="lk_b")
    r.add_argument("--backup")
    r.add_argument("--loader")
    r.set_defaults(fn=cmd_read)
    f = sub.add_parser("flash")
    f.add_argument("mode", choices=("identical", "write"))
    f.add_argument("--candidate-dir", required=True)
    f.add_argument("--base-dir")
    f.add_argument("--prior-identical")
    f.add_argument("--backup-copy")
    f.add_argument("--backup")
    f.add_argument("--loader")
    f.set_defaults(fn=cmd_flash)
    args = ap.parse_args()
    if not args.cmd:
        choice = pick(["ports", "uart", "read", "flash identical", "flash write"], "action")
        if choice.startswith("flash"):
            sys.exit("run: x28_flasher.py flash <identical|write> --candidate-dir DIR [--base-dir DIR]")
        args = ap.parse_args([choice])
    args.fn(args)


if __name__ == "__main__":
    main()
