#!/usr/bin/env python3
"""Step 7: restore one inactive-slot partition from the backup over USB, and prove it.

The ONLY script here that writes flash (risk/brick). Guardrails:
- only partitions of slot A (`*_a`), and only while the router reports `bootslot=b`
  over SSH; the denylist below is refused even if it ever ends in `_a`;
- the source is always the verified backup image (size and SHA-256 checked first);
- dry run by default; `--write` is needed to touch the device;
- one session: read the target plus guard partitions (its neighbours, its slot-B twin,
  misc, boot_para; all must match the backup, else abort), write, read everything back.
  One rewrite only if the write reported OK and only the target differs; a changed guard
  stops at once.

Writing back identical bytes proves the protocol and the address range, NOT that the
DA erases before programming (re-programming identical data passes either way). Prove
erase with different content on a spare unit before relying on a real restore.
Safety audit, 2026-10-22: NO-GO on the only unit until UART (#2) or a spare is available.

    python3 tools/recovery/write_verify.py lk_a            # dry run: prints the plan
    python3 tools/recovery/write_verify.py lk_a --write    # modem must be ON at start (SSH check)

Then power-cycle the modem when asked. Results go to private/usb-probe/<date>/.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from read_by_name import connect  # re-runs this script under the mtkclient venv
from common import DEFAULT_BACKUP, VENDOR_DA, backup_table, probe_dir, sha256_file
from read_verify import compare

DENY = {"preloader", "preloader_backup", "proinfo", "misc", "para", "expdb", "nvcfg", "nvdata",
        "protect1", "protect2", "seccfg", "boot_para", "nvram", "raw1", "raw2", "qraw",
        "user_config", "productinfo", "user_data"}


def active_slot():
    """Active slot from the running router's kernel command line, or None."""
    try:
        out = subprocess.run(["ssh", "-o", "ConnectTimeout=6", "-o", "BatchMode=yes", "router",
                              "cat /proc/cmdline"], capture_output=True, text=True, timeout=20).stdout
    except subprocess.TimeoutExpired:
        return None
    return next((w.split("=", 1)[1] for w in out.split() if w.startswith("bootslot=")), None)


def read_check(mtk, part, path):
    path.unlink(missing_ok=True)
    mtk.daloader.readflash(addr=part["offset"], length=part["size"], filename=str(path),
                           parttype=None, display=False)
    r = compare(path, [part])[0] if path.exists() else {"status": "NO DATA"}
    print(f"  read {path.name}: {r['status']}", flush=True)
    return r["status"] == "MATCH"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("partition", help="slot-A partition from the backup, e.g. lk_a")
    ap.add_argument("--write", action="store_true", help="actually write (default: dry run)")
    ap.add_argument("--backup", type=Path, default=DEFAULT_BACKUP)
    ap.add_argument("--loader", type=Path, default=VENDOR_DA if VENDOR_DA.is_file() else None)
    args = ap.parse_args()

    part = next((p for p in backup_table(args.backup) if p["name"] == args.partition), None)
    if part is None or not part["name"].endswith("_a") or part["name"] in DENY:
        sys.exit(f"refused: {args.partition!r} is not an allowed slot-A partition")
    image = Path(part["image"])
    if image.stat().st_size != part["size"] or sha256_file(image) != part["sha256"]:
        sys.exit(f"refused: backup image {image} does not match its recorded size/hash")
    table = backup_table(args.backup)
    by_name = {p["name"]: p for p in table}
    neighbours = [p for p in table if abs(p["index"] - part["index"]) == 1]
    guards = [*neighbours, *(by_name[n] for n in (part["name"][:-2] + "_b", "misc", "boot_para") if n in by_name)]
    slot = active_slot()
    print(f"partition {part['name']} (mtd{part['index']}): offset {part['offset']:#x}, size {part['size']:#x}")
    print(f"source    {image} sha256 {part['sha256']}")
    print(f"router    bootslot={slot}")
    print(f"guards    {', '.join(g['name'] for g in guards)} (must match the backup before and after)")
    if slot != "b":
        sys.exit("refused: router must be up and report bootslot=b (slot A must be inactive)")
    if not args.write:
        print("dry run: nothing sent to the device. Add --write to restore.")
        return

    loader = args.loader and args.loader.resolve()
    out = probe_dir()
    os.chdir(out)
    mtk = connect(out, loader)  # asks for the power cycle
    ok = False
    try:
        # neighbours catch a write that lands outside the range; the twin, misc and boot_para
        # catch a pending slot switch, which the cmdline check cannot see
        if not all(read_check(mtk, g, out / f"pre-{g['name']}.bin") for g in [part, *guards]):
            sys.exit("aborted before writing: a partition does not match the backup")
        for attempt in (1, 2):
            print(f"  WRITE-FLASH attempt {attempt}: {part['name']} from backup", flush=True)
            try:
                wrote = mtk.daloader.writeflash(addr=part["offset"], length=part["size"],
                                                filename=str(image), parttype=None, display=True)
                print(f"  write reported: {'OK' if wrote else 'FAILED'}", flush=True)
                ok = read_check(mtk, part, out / f"post-{part['name']}-{attempt}.bin")
            except Exception as e:  # a desynced session must not retry blindly
                print(f"  session error: {e!r}")
                wrote = ok = False
            if not all(read_check(mtk, g, out / f"post-{g['name']}-{attempt}.bin") for g in guards):
                ok = False
                print("  STOP: a guard partition changed; no retry")
                break
            if ok or not wrote:
                break
    finally:
        print("cycle the modem's power to boot it normally")
        mtk.port.close()
    print(f"RESTORE {'VERIFIED' if ok else 'NOT VERIFIED: do not rely on slot A; see the log'}")
    print(f"after it boots, confirm without the DA: ssh router 'cat /proc/cmdline; "
          f"sha256sum /dev/mtd{part['index']}'  (expect bootslot=b and {part['sha256'][:16]}...)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
