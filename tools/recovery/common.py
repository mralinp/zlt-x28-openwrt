"""Shared helpers for the ZLT X28 recovery scripts.

Run `python3 tools/recovery/common.py` for the self-check.
"""
import datetime
import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PRIVATE = REPO / "private"  # git-ignored: dumps, probe logs and chip IDs live here
MTK_HOME = PRIVATE / "mtkclient"
MTK = MTK_HOME / "venv" / "bin" / "mtk"

_MTD_LINE = re.compile(r'mtd(\d+): ([0-9a-f]+) ([0-9a-f]+) "([A-Za-z0-9_]+)"')


def parse_mtd(text):
    """Parse /proc/mtd. Offsets assume partitions sit back to back from 0, which the
    X28 layout does; read_verify.py proves it per partition by hash."""
    parts, offset = [], 0
    for line in text.splitlines()[1:]:
        m = _MTD_LINE.fullmatch(line.strip())
        if not m:
            raise ValueError(f"unexpected /proc/mtd line: {line!r}")
        index, size, erase, name = int(m[1]), int(m[2], 16), int(m[3], 16), m[4]
        if index != len(parts):
            raise ValueError(f"mtd{index} out of order")
        parts.append({"index": index, "name": name, "size": size,
                      "erase_size": erase, "offset": offset})
        offset += size
    return parts


def image_name(part):
    return f"mtd{part['index']:02d}-{part['name']}.bin"


DEFAULT_BACKUP = PRIVATE / "recovery" / "20261020-capture-prepared-20261021"


def backup_partition(backup, name):
    """Return (partition, expected SHA-256) for `name` from a verified backup."""
    mtd = next(p for p in (backup / "mtd.txt", backup / "metadata" / "mtd.txt") if p.exists())
    part = next((p for p in parse_mtd(mtd.read_text()) if p["name"] == name), None)
    if part is None:
        sys.exit(f"no partition {name!r} in {mtd}")
    sums = dict(reversed(l.split("  ", 1)) for l in (backup / "SHA256SUMS").read_text().splitlines())
    return part, sums[f"images/{image_name(part)}"]


def probe_dir():
    out = PRIVATE / "usb-probe" / datetime.date.today().strftime("%Y%m%d")
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    return out


def run_mtk(args, logname):
    """Run mtkclient, echo its output, and save a colour-free copy under
    private/usb-probe/<date>/ (the log holds the chip's ME_ID, so it stays private).
    The modem must be unpowered when this starts (mtkclient rejects a device that is
    already on USB); plug its power in once mtkclient says it is waiting."""
    if not MTK.exists():
        sys.exit("mtkclient not installed: run tools/recovery/setup_mtkclient.py")
    out = probe_dir()
    print(f"modem power must be OFF now; plug it in when mtkclient is waiting (log: {out / logname})",
          flush=True)
    proc = subprocess.Popen([str(MTK), *args], cwd=out, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    with open(out / logname, "w") as log:
        for line in proc.stdout:
            sys.stdout.write(line)
            log.write(re.sub(r"\x1b\[[0-9;]*m", "", line))
    return proc.wait(), out


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(1 << 20):
            h.update(block)
    return h.hexdigest()


if __name__ == "__main__":
    sample = ('dev:    size   erasesize  name\n'
              'mtd0: 00400000 00040000 "preloader"\n'
              'mtd1: 00200000 00040000 "preloader_backup"\n')
    p = parse_mtd(sample)
    assert [x["offset"] for x in p] == [0, 0x400000] and image_name(p[1]) == "mtd01-preloader_backup.bin"
    for bad in ('mtd1: 00200000 00040000 "x"', 'mtd0: zz 00040000 "x"'):
        try:
            parse_mtd("dev:\n" + bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    mtd = PRIVATE / "recovery/20261020-capture-prepared-20261021/metadata/mtd.txt"
    if mtd.exists():  # the real X28 table, when the private backup is present
        lk_b = next(x for x in parse_mtd(mtd.read_text()) if x["name"] == "lk_b")
        assert lk_b["offset"] == 0x1D800000, hex(lk_b["offset"])
    print("common.py self-check OK")
