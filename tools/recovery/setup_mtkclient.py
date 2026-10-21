#!/usr/bin/env python3
"""Step 4: install a pinned mtkclient into a private venv and patch it for the X28.

Needs git, libusb (`brew install libusb`) and Python >= 3.10 (tested: Homebrew 3.14):
    /opt/homebrew/bin/python3.14 tools/recovery/setup_mtkclient.py
    /opt/homebrew/bin/python3.14 tools/recovery/setup_mtkclient.py --commit <sha> --home private/mtkclient-x

Default: commit MTKCLIENT_COMMIT (common.py) into private/mtkclient-<sha7>, which the other
scripts use unless $X28_MTKCLIENT names another install.

Local changes to the installed copy (the source checkout stays pristine):
- remove fusepy/mfusepy: on macOS without libfuse they raise OSError at import,
  which mtkclient only expects as ImportError, so every command crashed at start;
- check_sla(): this board's DA answers the DA.SLA property query with nothing,
  and mtkclient called .decode() on False;
- get_hw_info(): this DA reports NAND with an empty page_parity_size field (unused);
- upload_da() (newer mtkclient only): building the optional DA extensions crashes on this
  DA (a function lookup returns None); skip the extensions instead of aborting.
"""
import argparse
import ctypes.util
import glob
import subprocess
import sys
from pathlib import Path

from common import MTK_HOME, MTKCLIENT_COMMIT

REPO_URL = "https://github.com/bkerler/mtkclient.git"

SLA_CALL = '        data = self.get_sys_property(key="DA.SLA", length=0x200000)\n'
EXT_CALL = "            if self.mtk.daloader.patch:\n                xdata = self.xmlft.patch()\n"
PATCHES = [  # (file under site-packages/mtkclient, old text, new text, required)
    ("Library/DA/xmlflash/xml_lib.py", SLA_CALL,
     SLA_CALL + "        if not data:  # X28 patch: DA returns no DA.SLA property\n"
                "            return False\n", True),
    ("Library/DA/xmlflash/xml_lib.py",
     'int(get_field(data, "page_parity_size"), 16)',
     'int(get_field(data, "page_parity_size") or "0", 16)  # X28 patch: empty on this DA', True),
    ("Library/DA/xmlflash/xml_lib.py", EXT_CALL,
     "            if self.mtk.daloader.patch:\n"
     "                try:  # X28 patch: extension builder fails on this DA; extensions are optional\n"
     "                    xdata = self.xmlft.patch()\n"
     "                except Exception as err:\n"
     "                    self.warning(f'DA XML extensions skipped: {err!r}')\n"
     "                    self.mtk.daloader.patch = False\n"
     "            if self.mtk.daloader.patch:\n", False),
]


def run(*cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--commit", default=MTKCLIENT_COMMIT, help="full mtkclient commit SHA to pin")
    ap.add_argument("--home", type=Path, default=MTK_HOME, help="install folder (src/ and venv/)")
    args = ap.parse_args()
    if sys.version_info < (3, 10):
        sys.exit("use Python >= 3.10, e.g. /opt/homebrew/bin/python3.14")
    if not (ctypes.util.find_library("usb-1.0") or glob.glob("/opt/homebrew/lib/libusb-1.0*.dylib")):
        sys.exit("libusb not found: brew install libusb")

    src, venv = args.home / "src", args.home / "venv"
    if not src.exists():
        run("git", "init", "-q", src)
        run("git", "-C", src, "fetch", "-q", "--depth", "1", REPO_URL, args.commit)
        run("git", "-C", src, "-c", "advice.detachedHead=false", "checkout", "-q", "FETCH_HEAD")
    head = subprocess.check_output(["git", "-C", src, "rev-parse", "HEAD"], text=True).strip()
    if head != args.commit:
        sys.exit(f"{src} is at {head}, expected {args.commit}")
    if not (venv / "bin" / "mtk").exists():
        run(sys.executable, "-m", "venv", venv)
        run(venv / "bin/pip", "install", "-q", src)
    run(venv / "bin/pip", "uninstall", "-y", "-q", "fusepy", "mfusepy")  # "Skipping" if absent

    pkg = next(venv.glob("lib/python3*/site-packages/mtkclient"))
    for rel, old, new, required in PATCHES:
        path = pkg / rel
        text = path.read_text()
        if new in text or "X28 patch" in text.split(old, 1)[-1][:120]:
            continue
        if text.count(old) != 1:
            if not required:
                continue  # code path absent in this mtkclient version
            sys.exit(f"patch target not found in {path}; mtkclient changed?")
        path.write_text(text.replace(old, new))
        print(f"patched {rel}")
    for cache in pkg.rglob("__pycache__"):
        for f in cache.iterdir():
            f.unlink()
    print(f"ready: {venv / 'bin' / 'mtk'}")


if __name__ == "__main__":
    main()
