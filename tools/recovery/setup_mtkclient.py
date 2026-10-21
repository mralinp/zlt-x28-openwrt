#!/usr/bin/env python3
"""Step 4: install a pinned mtkclient into private/mtkclient/venv and patch it for the X28.

Needs git, libusb (`brew install libusb`) and Python >= 3.10 (tested: Homebrew 3.14):
    /opt/homebrew/bin/python3.14 tools/recovery/setup_mtkclient.py

Local changes to the installed copy (the source checkout stays pristine):
- remove fusepy: on macOS without libfuse it raises OSError at import, which
  mtkclient only expects as ImportError, so every command crashed at start;
- check_sla(): this board's DA answers the DA.SLA property query with nothing,
  and mtkclient called .decode() on False;
- get_hw_info(): this DA reports NAND with an empty page_parity_size field (unused).
"""
import ctypes.util
import glob
import subprocess
import sys

from common import MTK, MTK_HOME

REPO_URL = "https://github.com/bkerler/mtkclient.git"
TAG, COMMIT = "v2.1.4.1", "5a863eece86fcaa97cb8325cf747e0aae3c307e4"

PATCHES = [  # (file under site-packages/mtkclient, old text, new text)
    ("Library/DA/xmlflash/xml_lib.py",
     '        data = self.get_sys_property(key="DA.SLA", length=0x200000)\n'
     "        data = data.decode('utf-8')\n",
     '        data = self.get_sys_property(key="DA.SLA", length=0x200000)\n'
     "        if not data:  # X28 patch: DA returns no DA.SLA property\n"
     "            return False\n"
     "        data = data.decode('utf-8')\n"),
    ("Library/DA/xmlflash/xml_lib.py",
     'int(get_field(data, "page_parity_size"), 16)',
     'int(get_field(data, "page_parity_size") or "0", 16)  # X28 patch: empty on this DA'),
]


def run(*cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, check=True)


def main():
    if sys.version_info < (3, 10):
        sys.exit("use Python >= 3.10, e.g. /opt/homebrew/bin/python3")
    if not (ctypes.util.find_library("usb-1.0") or glob.glob("/opt/homebrew/lib/libusb-1.0*.dylib")):
        sys.exit("libusb not found: brew install libusb")

    src, venv = MTK_HOME / "src", MTK_HOME / "venv"
    if not src.exists():
        run("git", "-c", "advice.detachedHead=false", "clone", "-q", "--depth", "1",
            "--branch", TAG, REPO_URL, src)
    head = subprocess.check_output(["git", "-C", src, "rev-parse", "HEAD"], text=True).strip()
    if head != COMMIT:
        sys.exit(f"{src} is at {head}, expected {TAG} = {COMMIT}")
    if not MTK.exists():
        run(sys.executable, "-m", "venv", venv)
        run(venv / "bin/pip", "install", "-q", src)
        run(venv / "bin/pip", "uninstall", "-y", "-q", "fusepy")

    pkg = next(venv.glob("lib/python3*/site-packages/mtkclient"))
    for rel, old, new in PATCHES:
        path = pkg / rel
        text = path.read_text()
        if new in text:
            continue
        if text.count(old) != 1:
            sys.exit(f"patch target not found in {path}; mtkclient changed?")
        path.write_text(text.replace(old, new))
        print(f"patched {rel}")
    for cache in pkg.rglob("__pycache__"):
        for f in cache.iterdir():
            f.unlink()
    print(f"ready: {MTK}")


if __name__ == "__main__":
    main()
