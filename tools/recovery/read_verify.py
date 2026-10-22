#!/usr/bin/env python3
"""Step 6: read one partition over USB (preloader + download agent) and compare it
with the SSH backup's hash.

Read-only: only `mtk ro` (READ-FLASH) is issued. The download agent is loaded into
the modem's RAM, which is cleared at power-off. A match proves that USB flash
access works and that the computed partition offset is right.

    python3 tools/recovery/read_verify.py lk_b [--backup DIR] [--loader DA.bin] [--debug]

Uses the vendor DA from private/ by default; mtkclient's bundled DA refuses reads on
the X28. For every partition in one session, use read_all.py.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from common import DEFAULT_BACKUP, VENDOR_DA, backup_table, run_mtk, sha256_file

PAGE = 4096


def compare(dump, parts):
    """Compare each partition's slice of `dump` with its backup hash (and image, on a mismatch)."""
    rows = []
    with open(dump, "rb") as f:
        base = parts[0]["offset"]
        for p in parts:
            f.seek(p["offset"] - base)
            data = f.read(p["size"])
            row = {"name": p["name"], "offset": p["offset"], "size": p["size"]}
            if len(data) != p["size"]:
                row["status"] = f"SHORT ({len(data)} bytes)"
            elif hashlib.sha256(data).hexdigest() == p["sha256"]:
                row["status"] = "MATCH"
            else:
                ref = Path(p["image"]).read_bytes()
                pages = [i for i in range(0, p["size"], PAGE) if data[i:i + PAGE] != ref[i:i + PAGE]]
                first = next(i for i in range(pages[0], pages[0] + PAGE) if data[i] != ref[i])
                row.update(status="DIFF", first_diff=first, diff_pages=len(pages),
                           usb_erased_pages=sum(data[i:i + PAGE].count(0xFF) == PAGE for i in pages))
            rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("partition", help="name from /proc/mtd, e.g. lk_b")
    ap.add_argument("--backup", type=Path, default=DEFAULT_BACKUP,
                    help="verified backup holding mtd.txt and SHA256SUMS")
    ap.add_argument("--loader", type=Path, default=VENDOR_DA if VENDOR_DA.is_file() else None,
                    help="download agent file (default: the vendor DA in private/, if present)")
    ap.add_argument("--debug", action="store_true", help="mtkclient --debugmode (logs DA XML replies)")
    args = ap.parse_args()

    parts = [p for p in backup_table(args.backup) if p["name"] == args.partition]
    if not parts:
        sys.exit(f"no partition {args.partition!r} in {args.backup}")
    start, length = parts[0]["offset"], parts[-1]["offset"] + parts[-1]["size"] - parts[0]["offset"]

    tag = f"-{args.loader.stem}" if args.loader else ""
    outfile = f"{args.partition}-usb{tag}.bin"
    mtk_args = ["ro", hex(start), hex(length), outfile, "--skipwdt"]
    if args.loader:
        if not args.loader.is_file():
            sys.exit(f"no such loader: {args.loader}")
        mtk_args += ["--loader", str(args.loader.resolve())]  # mtk runs from the probe dir
    if args.debug:
        mtk_args.append("--debugmode")
    print(f"{args.partition}: {len(parts)} partition(s), offset {start:#x}, length {length:#x}")
    code, out = run_mtk(mtk_args, f"read-{args.partition}{tag}.log")

    got = out / outfile
    print("cycle the modem's power to boot it normally")
    if not got.exists() or got.stat().st_size != length:
        sys.exit(f"incomplete read (mtk exit {code}, {got.stat().st_size if got.exists() else 0} bytes); see the log")
    rows = compare(got, parts)
    for r in rows:
        extra = (f"  first diff +{r['first_diff']:#x}, {r['diff_pages']} pages differ"
                 f" ({r['usb_erased_pages']} erased on USB side)") if r["status"] == "DIFF" else ""
        print(f"{r['name']:<17} {r['offset']:#012x} {r['size']:#011x}  {r['status']}{extra}")
    (out / f"compare-{args.partition}{tag}.json").write_text(json.dumps(rows, indent=1) + "\n")
    matched = sum(r["status"] == "MATCH" for r in rows)
    print(f"{matched}/{len(rows)} MATCH; report: {out / f'compare-{args.partition}{tag}.json'}")
    sys.exit(0 if matched == len(rows) else 1)


if __name__ == "__main__":
    main()
