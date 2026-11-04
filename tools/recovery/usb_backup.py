#!/usr/bin/env python3
"""Full read-only backup of the X28's NAND over USB (download agent), in the layout the guarded tools read (#284).

Reads every partition of the fixed X28 layout (x28-mtd.txt) twice, keeps it only if both reads agree, and writes
OUT/images/*, OUT/mtd.txt, OUT/SHA256SUMS, OUT/complete-captured-partitions.tar and OUT/ARCHIVE.sha256. The router must be
unpowered when this starts; plug it in when mtkclient is waiting. Nothing is written to the router. Re-run with the same
--out to resume after an interruption.

    python3 tools/recovery/usb_backup.py --out DIR --loader DA_BR.bin [--no-verify]
"""
import argparse
import json
import os
import sys
import tarfile
import time
from pathlib import Path

from common import fmt_eta, image_name, parse_mtd, sha256_file

LAYOUT = Path(__file__).with_name("x28-mtd.txt")
PARTIAL = "SHA256SUMS.partial"


def write_backup(out, parts, read, verify=True, say=print):
    """read(part, path) -> bool fills path with the partition's bytes. Returns the list of (sha256, relative path)."""
    images = out / "images"
    images.mkdir(parents=True, exist_ok=True)
    partial = out / PARTIAL
    done = dict(reversed(l.split("  ", 1)) for l in partial.read_text().splitlines()) if partial.exists() else {}
    total, finished, started = sum(p["size"] for p in parts), 0, time.monotonic()
    sums = []
    for i, p in enumerate(parts, 1):
        name, path = image_name(p), images / image_name(p)
        rel = f"images/{name}"
        if rel in done and path.is_file() and path.stat().st_size == p["size"] and sha256_file(path) == done[rel]:
            say(f"[{i}/{len(parts)}] {p['name']}: already read, kept")
            sums.append((done[rel], rel))
            finished += p["size"]
            continue
        say(f"[{i}/{len(parts)}] reading {p['name']} ({p['size'] / 2**20:.1f} MiB)")
        if not read(p, path) or path.stat().st_size != p["size"]:
            raise RuntimeError(f"read of {p['name']} failed or came back short; run again with the same --out to resume")
        digest = sha256_file(path)
        if verify:
            again = out / (name + ".verify")
            if not read(p, again) or sha256_file(again) != digest:
                again.unlink(missing_ok=True)
                raise RuntimeError(f"two reads of {p['name']} disagree; nothing was kept for it")
            again.unlink()
        with partial.open("a") as f:
            f.write(f"{digest}  {rel}\n")
        sums.append((digest, rel))
        finished += p["size"]
        rate = finished / max(time.monotonic() - started, 1e-9)
        say(f"  ok  {digest[:12]}   overall {finished / total:6.1%}  ETA {fmt_eta((total - finished) / rate)}")
    return sums


def seal(out, sums, layout_text):
    """Write the files the guarded tools expect and the archive used as the second copy."""
    (out / "mtd.txt").write_text(layout_text)
    (out / "SHA256SUMS").write_text("".join(f"{d}  {r}\n" for d, r in sums))
    archive = out / "complete-captured-partitions.tar"
    with tarfile.open(archive, "w") as tar:
        for _, rel in sums:
            tar.add(out / rel, arcname=rel)
        tar.add(out / "mtd.txt", arcname="mtd.txt")
        tar.add(out / "SHA256SUMS", arcname="SHA256SUMS")
    (out / "ARCHIVE.sha256").write_text(f"{sha256_file(archive)}  {archive.name}\n")
    (out / PARTIAL).unlink(missing_ok=True)
    return archive


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--loader", type=Path, required=True, help="download agent file (DA_BR.bin)")
    ap.add_argument("--no-verify", action="store_true", help="read each partition once (half the time, no cross-check)")
    args = ap.parse_args()
    layout_text = LAYOUT.read_text()
    parts = parse_mtd(layout_text)
    print(f"{len(parts)} partitions, {sum(p['size'] for p in parts) / 2**20:.0f} MiB"
          f"{'' if args.no_verify else ', each read twice'}; writing to {args.out}")
    args.out.mkdir(parents=True, exist_ok=True)
    from read_by_name import connect, problems  # re-runs this script under the mtkclient venv when not frozen
    os.chdir(args.out)  # mtkclient drops its hwparam/state files in the working directory
    mtk = connect(args.out.resolve(), args.loader.resolve())
    try:
        def read(p, path):
            problems.attach()
            return mtk.daloader.readflash(addr=p["offset"], length=p["size"], filename=str(path), parttype=None,
                                          display=p["size"] >= 4 << 20) is True
        sums = write_backup(args.out.resolve(), parts, read, verify=not args.no_verify)
    finally:
        print("cycle the modem's power to boot it normally")
        mtk.port.close()
    archive = seal(args.out.resolve(), sums, layout_text)
    print(f"backup complete: {len(sums)} partitions, archive {archive} ({sha256_file(archive)[:12]})")
    problems.report()


if __name__ == "__main__":
    main()
