#!/usr/bin/env python3
"""Step 7: check an identical rewrite of one inactive-slot partition over USB.

The ONLY script here that writes flash (risk/brick). Guardrails:
- only partitions of slot A (`*_a`), and only while the router reports `bootslot=b`
  over SSH; the denylist below is refused even if it ever ends in `_a`;
- the source is always the verified backup image (size and SHA-256 checked first);
- dry run by default; `--write` is needed to touch the device;
- one session: read the target plus guard partitions (its neighbours, its slot-B twin,
  misc, boot_para; all must match the backup, else abort), write, read everything back.
  A failed write, read, or guard check stops; there is no automatic retry.

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
import tempfile
from pathlib import Path

from common import DEFAULT_BACKUP, VENDOR_DA, backup_table, probe_dir, sha256_file, parse_mtd
from read_verify import compare

DENY = {"preloader", "preloader_backup", "proinfo", "misc", "para", "expdb", "nvcfg", "nvdata",
        "protect1", "protect2", "seccfg", "boot_para", "nvram", "raw1", "raw2", "qraw",
        "user_config", "productinfo", "user_data"}


def active_slot(table):
    """Active slot only when key-only SSH succeeds and the complete live layout matches."""
    try:
        result = subprocess.run(["ssh", "-o", "ConnectTimeout=6", "-o", "BatchMode=yes",
                                 "-o", "StrictHostKeyChecking=yes", "router",
                                 "cat /proc/cmdline /proc/mtd"],
                                capture_output=True, text=True, timeout=20)
    except (subprocess.TimeoutExpired, OSError):
        return None
    lines = result.stdout.splitlines()
    if result.returncode or len(lines) < 2:
        return None
    slots = [w.split("=", 1)[1] for w in lines[0].split() if w.startswith("bootslot=")]
    if len(slots) != 1 or slots[0] not in ("a", "b"):
        return None
    try:
        live = parse_mtd("\n".join(lines[1:]))
    except ValueError:
        return None
    expected = [{k: p[k] for k in ("index", "name", "size", "erase_size", "offset")} for p in table]
    return slots[0] if live == expected else None


def read_check(mtk, part, path):
    path.unlink(missing_ok=True)
    read_ok = mtk.daloader.readflash(addr=part["offset"], length=part["size"], filename=str(path),
                                     parttype=None, display=False)
    if read_ok is not True:
        r = {"status": "READ FAILED"}
    elif not path.is_file() or path.stat().st_size != part["size"]:
        r = {"status": "MISSING OR WRONG SIZE"}
    else:
        r = compare(path, [part])[0]
    print(f"  read {path.name}: {r['status']}", flush=True)
    return r["status"] == "MATCH"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("partition", help="slot-A partition from the backup, e.g. lk_a")
    ap.add_argument("--write", action="store_true", help="actually write (default: dry run)")
    ap.add_argument("--backup", type=Path, default=DEFAULT_BACKUP)
    ap.add_argument("--loader", type=Path, default=VENDOR_DA if VENDOR_DA.is_file() else None)
    args = ap.parse_args()

    args.backup = args.backup.resolve(strict=True)
    table = backup_table(args.backup)
    part = next((p for p in table if p["name"] == args.partition), None)
    if part is None or not part["name"].endswith("_a") or part["name"] in DENY:
        sys.exit(f"refused: {args.partition!r} is not an allowed slot-A partition")
    image = Path(part["image"]).resolve(strict=True)
    if image.stat().st_size != part["size"] or sha256_file(image) != part["sha256"]:
        sys.exit(f"refused: backup image {image} does not match its recorded size/hash")
    by_name = {p["name"]: p for p in table}
    neighbours = [p for p in table if abs(p["index"] - part["index"]) == 1]
    required = (part["name"][:-2] + "_b", "misc", "boot_para")
    if len(by_name) != len(table) or len(neighbours) != 2 or any(n not in by_name for n in required):
        sys.exit("refused: incomplete or duplicate partition layout; required guards are missing")
    guards = [*neighbours, *(by_name[n] for n in required)]
    slot = active_slot(table)
    print(f"partition {part['name']} (mtd{part['index']}): offset {part['offset']:#x}, size {part['size']:#x}")
    print(f"source    {image} sha256 {part['sha256']}")
    print(f"router    bootslot={slot}")
    print(f"guards    {', '.join(g['name'] for g in guards)} (must match the backup before and after)")
    if slot != "b":
        sys.exit("refused: router must report one bootslot=b and a matching full partition layout")
    if not args.write:
        print("dry run: no USB command or write issued; identical rewrite requires --write.")
        return

    if not args.loader or not args.loader.is_file():
        sys.exit("refused: an existing tested download agent is required for a write")
    loader = args.loader.resolve()
    from read_by_name import connect, problems  # hardware dependencies only after preflight
    out = Path(tempfile.mkdtemp(prefix=f"restore-{part['name']}-", dir=probe_dir()))
    os.chdir(out)
    mtk = connect(out, loader)  # asks for the power cycle
    ok = False
    try:
        # neighbours catch a write that lands outside the range; the twin, misc and boot_para
        # catch a pending slot switch, which the cmdline check cannot see
        if not all(read_check(mtk, g, out / f"pre-{g['name']}.bin") for g in [part, *guards]):
            sys.exit("aborted before writing: a partition does not match the backup")
        if image.stat().st_size != part["size"] or sha256_file(image) != part["sha256"]:
            sys.exit("aborted before writing: backup source changed during preflight")
        print(f"  WRITE-FLASH: {part['name']} from backup (one attempt)", flush=True)
        try:
            wrote = mtk.daloader.writeflash(addr=part["offset"], length=part["size"],
                                            filename=str(image), parttype=None, display=True)
            print(f"  write reported: {'OK' if wrote is True else 'FAILED'}", flush=True)
            matched = read_check(mtk, part, out / f"post-{part['name']}.bin")
            ok = wrote is True and matched
            if not all([read_check(mtk, g, out / f"post-{g['name']}.bin") for g in guards]):
                ok = False
                print("  STOP: a guard partition failed verification; no retry")
        except Exception as e:
            print(f"  session error: {e!r}; no retry")
            ok = False
    finally:
        if ok:
            print("cycle the modem's power to boot it normally")
        else:
            print("STOP: unverified result; review recovery logs before any further write or reboot")
        mtk.port.close()
        problems.report()
    print(f"IDENTICAL REWRITE {'VERIFIED' if ok else 'NOT VERIFIED: do not rely on slot A; see the log'}")
    print(f"after it boots, confirm without the DA: ssh router 'cat /proc/cmdline; "
          f"sha256sum /dev/mtd{part['index']}'  (expect bootslot=b and {part['sha256'][:16]}...)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
