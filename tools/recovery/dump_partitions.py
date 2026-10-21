#!/usr/bin/env python3
"""Step 1: read-only backup of every NAND partition over SSH.

Streams `nanddump --bb=padbad -q /dev/mtdN` (main data, ECC-corrected, bad blocks
padded with 0xFF, no OOB) from the `ssh router` host into gzip files, hashing the raw
bytes on the way. Nothing is written to the router.

    python3 tools/recovery/dump_partitions.py [--out private/backups/YYYYMMDD]
"""
import argparse
import datetime
import gzip
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from common import PRIVATE, image_name, parse_mtd

SSH = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "router"]
ECC_NOTICE = re.compile(r"ECC: \d+ corrected bitflip\(s\) at offset 0x[0-9a-fA-F]+")


def remote(command):
    return subprocess.check_output(SSH + [command], timeout=30)


def dump(part, out):
    path = out / (image_name(part) + ".gz")
    temp = path.with_suffix(".gz.partial")
    proc = subprocess.Popen(SSH + [f"nanddump --bb=padbad -q /dev/mtd{part['index']}"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    digest, count, started = hashlib.sha256(), 0, time.monotonic()
    try:
        with gzip.open(temp, "wb", compresslevel=1) as f:
            while chunk := proc.stdout.read(1 << 20):
                count += len(chunk)
                digest.update(chunk)
                f.write(chunk)
        notices = [l for l in proc.stderr.read().decode(errors="replace").splitlines() if l.strip()]
        code = proc.wait(timeout=30)
        # corrected bitflips are normal on NAND; anything else in stderr is not
        if code or count != part["size"] or not all(ECC_NOTICE.fullmatch(l) for l in notices):
            raise RuntimeError(f"{part['name']}: exit={code} bytes={count}/{part['size']} {notices[:3]}")
        temp.replace(path)
    except BaseException:
        proc.kill()
        proc.wait()
        temp.unlink(missing_ok=True)
        raise
    return {**part, "file": path.name, "bytes_read": count, "sha256": digest.hexdigest(),
            "ecc_notices": notices, "seconds": round(time.monotonic() - started, 1)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path,
                    default=PRIVATE / "backups" / datetime.date.today().strftime("%Y%m%d"))
    out = ap.parse_args().out
    out.mkdir(mode=0o700, parents=True, exist_ok=False)

    mtd_text = remote("cat /proc/mtd").decode()
    (out / "mtd.txt").write_text(mtd_text)
    for name, cmd in [("cmdline.txt", "cat /proc/cmdline"),
                      ("openwrt-release.txt", "cat /etc/openwrt_release")]:
        (out / name).write_bytes(remote(cmd))

    manifest = {"device": "ZLT X28", "date": datetime.date.today().isoformat(),
                "command": "nanddump --bb=padbad -q /dev/mtdN", "partitions": []}
    for part in parse_mtd(mtd_text):
        print(f"mtd{part['index']:<2} {part['name']:<18} {part['size'] / 2**20:7.1f} MiB", flush=True)
        manifest["partitions"].append(dump(part, out))
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"done: {len(manifest['partitions'])} partitions in {out}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"backup stopped: {e}")
