#!/usr/bin/env python3
"""Step 3: log USB devices appearing and disappearing on the Mac (macOS only).

Start it, then power-cycle the modem. The MediaTek preloader port (0e8d:2000)
is only present for about a second after power-on, so it polls every 50 ms.

    python3 tools/recovery/usb_watch.py [--seconds 300]
"""
import argparse
import glob
import plistlib
import subprocess
import time

NOTE = {0x0E8D: "<- MediaTek preloader/BROM: recovery port", 0x2C7C: "<- Quectel Linux USB gadget"}


def devices():
    out = subprocess.run(["ioreg", "-p", "IOUSB", "-l", "-a"], capture_output=True).stdout
    found = set()

    def walk(node):
        if "idVendor" in node:
            found.add((node["idVendor"], node.get("idProduct", 0),
                       node.get("USB Product Name", node.get("IORegistryEntryName", "?"))))
        for child in node.get("IORegistryEntryChildren", []):
            walk(child)

    if out:
        walk(plistlib.loads(out))
    return found | {(None, None, p) for p in glob.glob("/dev/cu.usb*")}


def label(dev):
    vid, pid, name = dev
    return name if vid is None else f"{vid:04x}:{pid:04x} {name} {NOTE.get(vid, '')}".rstrip()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seconds", type=float, default=300)
    end = time.time() + ap.parse_args().seconds
    prev = devices()
    print("present:", *sorted(map(label, prev)), sep="\n  ", flush=True)
    while time.time() < end:
        cur = devices()
        stamp = time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"
        for d in cur - prev:
            print(stamp, "+", label(d), flush=True)
        for d in prev - cur:
            print(stamp, "-", label(d), flush=True)
        prev = cur
        time.sleep(0.05)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
