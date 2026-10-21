#!/usr/bin/env python3
"""Step 6: read one partition over USB (preloader + download agent) and compare
it with the SSH backup's hash.

Read-only: only `mtk ro` (READ-FLASH) is issued. The download agent is loaded into
the modem's RAM, which is cleared at power-off. A match proves that USB flash
access works and that the computed partition offset is right.

    python3 tools/recovery/read_verify.py lk_b [--backup DIR] [--loader DA.bin] [--debug]

Uses the vendor DA from private/ by default; mtkclient's bundled DA refuses reads on the X28.
"""
import argparse
import sys
from pathlib import Path

from common import DEFAULT_BACKUP, VENDOR_DA, backup_partition, run_mtk, sha256_file


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("partition", help="name from /proc/mtd, e.g. lk_b")
    ap.add_argument("--backup", type=Path, default=DEFAULT_BACKUP,
                    help="verified backup holding mtd.txt and SHA256SUMS")
    ap.add_argument("--loader", type=Path, default=VENDOR_DA if VENDOR_DA.is_file() else None,
                    help="download agent file (default: the vendor DA in private/, if present)")
    ap.add_argument("--debug", action="store_true", help="mtkclient --debugmode (logs DA XML replies)")
    args = ap.parse_args()

    part, expected = backup_partition(args.backup, args.partition)

    tag = f"-{args.loader.stem}" if args.loader else ""
    outfile = f"{part['name']}-usb{tag}.bin"
    mtk_args = ["ro", hex(part["offset"]), hex(part["size"]), outfile, "--skipwdt"]
    if args.loader:
        if not args.loader.is_file():
            sys.exit(f"no such loader: {args.loader}")
        mtk_args += ["--loader", str(args.loader.resolve())]  # mtk runs from the probe dir
    if args.debug:
        mtk_args.append("--debugmode")
    print(f"{part['name']}: offset {part['offset']:#x}, size {part['size']:#x}, expect {expected}")
    code, out = run_mtk(mtk_args, f"read-{part['name']}{tag}.log")

    got = out / outfile
    print("cycle the modem's power to boot it normally")
    if not got.exists():
        sys.exit(f"no data read (mtk exit {code}); see the log")
    actual = sha256_file(got)
    print(f"read     {actual}\nbackup   {expected}\n{'MATCH' if actual == expected else 'MISMATCH'}")
    sys.exit(0 if actual == expected else 1)


if __name__ == "__main__":
    main()
