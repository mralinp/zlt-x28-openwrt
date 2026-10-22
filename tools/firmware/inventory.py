#!/usr/bin/env python3
"""Offline inventory of X28 firmware: kernel config, kernel modules, packages and their files.

    # kernel config embedded in a boot partition image (CONFIG_IKCONFIG), on the host:
    python3 tools/firmware/inventory.py kconfig private/recovery/<backup>/images/mtd40-boot_b.bin out.config

    # modules and packages of an extracted rootfs. Run it on a case-sensitive filesystem,
    # e.g. the Docker volume from the rootfs extraction (no network, read-only):
    docker run --rm --network none -v x28-rootfs-b-analysis-20261021:/r:ro -v "$PWD/tools/firmware:/t:ro" \
        x28-firmware-tools:local python3 /t/inventory.py rootfs /r/rootfs > private/firmware/inventory.json

Reads only; never executes anything from the firmware.
"""
import json
import os
import re
import struct
import sys
import zlib

MODINFO = re.compile(rb"(?:^|\x00)(name|vermagic|depends|license|description|srcversion)=([^\x00]*)")


def kconfig(boot_img, out):
    d = open(boot_img, "rb").read()
    if d[:8] != b"ANDROID!":
        sys.exit("not an Android boot image")
    kernel_size, page = struct.unpack_from("<I", d, 8)[0], struct.unpack_from("<I", d, 0x24)[0]
    k = d[page:page + kernel_size]
    raw = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(k[k.find(b"\x1f\x8b\x08"):], 128 << 20)
    i = raw.find(b"IKCFG_ST")
    if i < 0:
        sys.exit("kernel has no embedded config (CONFIG_IKCONFIG not set)")
    cfg = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(raw[i + 8:], 8 << 20)
    banner = re.search(rb"Linux version [ -~]+", raw)
    open(out, "wb").write(cfg)
    options = cfg.count(b"\nCONFIG_")
    print(f"{out}: {options} options set; {banner.group().decode() if banner else ''}")


def rootfs(root):
    info_dir = os.path.join(root, "usr/lib/opkg/info")
    status_path = os.path.join(root, "usr/lib/opkg/status")
    packages = {}
    for block in (open(status_path).read() if os.path.exists(status_path) else "").split("\n\n"):
        f = dict(re.findall(r"^([A-Za-z-]+): (.*)$", block, re.M))
        if "Package" in f:
            packages[f["Package"]] = {"version": f.get("Version"), "arch": f.get("Architecture"), "files": 0}
    owner = {}
    for f in sorted(os.listdir(info_dir)) if os.path.isdir(info_dir) else []:
        if f.endswith(".list"):
            for line in open(os.path.join(info_dir, f)):
                owner[line.strip()] = f[:-5]
    files, modules = [], []
    for dp, _, names in os.walk(root):
        rel = "/" + os.path.relpath(dp, root)
        if rel.startswith(("/proc", "/sys", "/dev", "/tmp", "/overlay", "/rom")):
            continue
        for n in names:
            p = os.path.join(dp, n)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            path = os.path.normpath(os.path.join(rel, n))
            data = open(p, "rb").read()
            pkg = owner.get(path)
            if pkg in packages:
                packages[pkg]["files"] += 1
            files.append({"path": path, "size": len(data), "pkg": pkg, "elf": data[:4] == b"\x7fELF"})
            if n.endswith(".ko"):
                mi = {}
                for m in MODINFO.finditer(data):
                    mi.setdefault(m[1].decode(), m[2].decode(errors="replace"))
                modules.append({"path": path, "size": len(data), "pkg": pkg, **mi})
    json.dump({"packages": packages, "modules": modules, "files": files}, sys.stdout, indent=0)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "kconfig":
        kconfig(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "rootfs":
        rootfs(sys.argv[2])
    else:
        sys.exit(__doc__)
