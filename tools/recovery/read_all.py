#!/usr/bin/env python3
"""Step 6b: read every partition over USB in one session and compare each with the backup.

One download-agent session, one READ-FLASH per partition, each written to
private/usb-probe/<date>/all/mtdNN-<name>.bin and compared at once. Read-only.
A single ~1 GiB READ-FLASH died with a USB pipe error after 236 MiB, so the reads
are split per partition; --from resumes at a partition after an interruption.
DIFF is expected for partitions the firmware writes while running (nvdata,
protect1/2, user_data, ...). The modem must be unpowered when this starts.

    python3 tools/recovery/read_all.py [--from md1img_a] [--backup DIR] [--loader DA.bin]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

from read_by_name import connect, problems  # re-runs this script under the mtkclient venv
from common import DEFAULT_BACKUP, VENDOR_DA, backup_table, fmt_eta, image_name, probe_dir
from read_verify import compare


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from", dest="start", help="first partition to read (resume)")
    ap.add_argument("--backup", type=Path, default=DEFAULT_BACKUP)
    ap.add_argument("--loader", type=Path, default=VENDOR_DA if VENDOR_DA.is_file() else None,
                    help="download agent file (default: the vendor DA in private/, if present)")
    args = ap.parse_args()

    parts = backup_table(args.backup)
    if args.start:
        names = [p["name"] for p in parts]
        if args.start not in names:
            sys.exit(f"no partition {args.start!r}")
        parts = parts[names.index(args.start):]
    print(f"{len(parts)} partitions, {sum(p['size'] for p in parts) / 2**20:.1f} MiB, starting at {parts[0]['name']}")

    loader = args.loader and args.loader.resolve()
    out = probe_dir()
    (out / "all").mkdir(exist_ok=True)
    os.chdir(out)
    mtk = connect(out, loader)
    rows, report = [], out / "all" / "compare.json"
    total, done, started = sum(p["size"] for p in parts), 0, time.monotonic()
    try:
        for i, p in enumerate(parts, 1):
            print(f"[{i}/{len(parts)}] reading {p['name']} ({p['size'] / 2**20:.1f} MiB) ...", flush=True)
            path = out / "all" / image_name(p)
            problems.attach()
            try:
                ok = mtk.daloader.readflash(addr=p["offset"], length=p["size"], filename=str(path),
                                            parttype=None, display=p["size"] >= 4 << 20)
            except Exception as e:  # USB errors end the session; report and stop cleanly
                problems.found.append(f"EXCEPTION reading {p['name']}: {e!r}")
                ok = False
            got = path.stat().st_size if path.exists() else 0
            if not ok or got != p["size"]:
                print(f"  FAILED: {got:#x} of {p['size']:#x} bytes; resume with --from {p['name']}")
                break
            r = compare(path, [p])[0]
            rows.append(r)
            done += p["size"]
            rate = done / (time.monotonic() - started)
            extra = (f"  first diff +{r['first_diff']:#x}, {r['diff_pages']} pages differ"
                     f" ({r['usb_erased_pages']} erased on USB side)") if r["status"] == "DIFF" else ""
            print(f"  {r['status']:<5} {r['offset']:#012x} {r['size']:#011x}{extra}\n"
                  f"  overall {done / total:6.1%}  {rate / 2**20:.2f} MB/s  ETA {fmt_eta((total - done) / rate)}",
                  flush=True)
            report.write_text(json.dumps(rows, indent=1) + "\n")
    finally:
        print("cycle the modem's power to boot it normally")
        mtk.port.close()

    matched = sum(r["status"] == "MATCH" for r in rows)
    print(f"\n{matched}/{len(rows)} read partitions MATCH ({len(parts) - len(rows)} not read) "
          f"in {fmt_eta(time.monotonic() - started)}; report: {report}")
    diffs = [r["name"] for r in rows if r["status"] != "MATCH"]
    print(f"DIFF: {', '.join(diffs) or 'none'}")
    problems.report()


if __name__ == "__main__":
    main()
