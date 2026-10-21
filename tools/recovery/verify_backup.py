#!/usr/bin/env python3
"""Step 2: verify a partition backup and unpack it to raw images.

Checks every gzip capture against the size and SHA-256 recorded at dump time,
writes `images/mtdNN-<name>.bin` and `SHA256SUMS`. Refuses an incomplete set.
Creates no flash image or command.

    python3 tools/recovery/verify_backup.py private/backups/YYYYMMDD
"""
import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

from common import image_name


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("backup", type=Path)
    root = ap.parse_args().backup
    parts = json.loads((root / "manifest.json").read_text())["partitions"]
    if sorted(p["index"] for p in parts) != list(range(len(parts))):
        sys.exit("manifest is missing partitions")

    images = root / "images"
    images.mkdir(mode=0o700, exist_ok=True)
    sums = []
    for p in sorted(parts, key=lambda p: p["index"]):
        expected = p.get("sha256") or p["sha256_uncompressed"]  # older manifests use the long key
        raw = images / image_name(p)
        h, size = hashlib.sha256(), 0
        with gzip.open(root / p["file"], "rb") as src, open(raw, "wb") as dst:
            while block := src.read(1 << 20):
                size += len(block)
                h.update(block)
                dst.write(block)
        if size != p["size"] or h.hexdigest() != expected:
            raw.unlink()
            sys.exit(f"MISMATCH mtd{p['index']} {p['name']}: {size} bytes, {h.hexdigest()}")
        sums.append(f"{expected}  images/{raw.name}\n")
        print(f"ok mtd{p['index']:<2} {p['name']}")
    (root / "SHA256SUMS").write_text("".join(sums))
    print(f"verified {len(sums)} partitions, {sum(p['size'] for p in parts)} bytes")


if __name__ == "__main__":
    main()
