#!/usr/bin/env python3
"""Step 6: read one partition over USB (preloader + download agent) and compare
it with the SSH backup's hash.

Read-only: only `mtk ro` (READ-FLASH) is issued. The download agent is loaded into
the modem's RAM, which is cleared at power-off. A match proves that USB flash
access works and that the computed partition offset is right.

    python3 tools/recovery/read_verify.py lk_b [--backup DIR] [--debug]
"""
import argparse
import sys
from pathlib import Path

from common import PRIVATE, image_name, parse_mtd, run_mtk, sha256_file

DEFAULT_BACKUP = PRIVATE / "recovery" / "20261020-capture-prepared-20261021"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("partition", help="name from /proc/mtd, e.g. lk_b")
    ap.add_argument("--backup", type=Path, default=DEFAULT_BACKUP,
                    help="verified backup holding mtd.txt and SHA256SUMS")
    ap.add_argument("--debug", action="store_true", help="mtkclient --debugmode (logs DA XML replies)")
    args = ap.parse_args()

    mtd = next(p for p in (args.backup / "mtd.txt", args.backup / "metadata" / "mtd.txt") if p.exists())
    part = next((p for p in parse_mtd(mtd.read_text()) if p["name"] == args.partition), None)
    if part is None:
        sys.exit(f"no partition {args.partition!r} in {mtd}")
    sums = dict(reversed(l.split("  ", 1)) for l in (args.backup / "SHA256SUMS").read_text().splitlines())
    expected = sums[f"images/{image_name(part)}"]

    outfile = f"{part['name']}-usb.bin"
    mtk_args = ["ro", hex(part["offset"]), hex(part["size"]), outfile, "--skipwdt"]
    print(f"{part['name']}: offset {part['offset']:#x}, size {part['size']:#x}, expect {expected}")
    code, out = run_mtk(mtk_args + (["--debugmode"] if args.debug else []), f"read-{part['name']}.log")

    got = out / outfile
    print("cycle the modem's power to boot it normally")
    if not got.exists():
        sys.exit(f"no data read (mtk exit {code}); see the log")
    actual = sha256_file(got)
    print(f"read     {actual}\nbackup   {expected}\n{'MATCH' if actual == expected else 'MISMATCH'}")
    sys.exit(0 if actual == expected else 1)


if __name__ == "__main__":
    main()
