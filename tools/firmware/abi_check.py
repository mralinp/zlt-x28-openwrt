#!/usr/bin/env python3
"""Can vendor binaries from the stock 19.07 rootfs run on a newer OpenWrt userspace?

For the given vendor binaries and their library closure in the OLD rootfs, finds every
stock library they import (by soname) and every symbol they take from it, then checks the
NEW userspace (a rootfs tarball and/or .ipk packages): is the soname there, and does it
export every needed symbol? Everything is read in memory; nothing is extracted or run.

    python3 tools/firmware/abi_check.py OLD_ROOTFS_DIR NEW.tar.gz [NEW.ipk ...] -- /usr/bin/ccci_mdinit ...

Run it where OLD_ROOTFS_DIR is case-sensitive (the Docker volume); see docs/FIRMWARE-INVENTORY.md.
"""
import io
import os
import sys
import tarfile

from inventory import elf_dynamic, elf_symbols


def new_libs(archives):
    """{basename: bytes} of every shared library in the given tar.gz / .ipk files."""
    libs = {}

    def walk(tf):
        for m in tf.getmembers():
            n = os.path.basename(m.name)
            if m.isfile() and ".so" in n:
                data = tf.extractfile(m).read()
                if data[:4] == b"\x7fELF":
                    libs[n] = data
            elif m.isfile() and n == "data.tar.gz":  # .ipk payload
                walk(tarfile.open(fileobj=io.BytesIO(tf.extractfile(m).read())))
    for a in archives:
        walk(tarfile.open(a))
    return libs


def main():
    sep = sys.argv.index("--")
    old_root, archives, roots = sys.argv[1], sys.argv[2:sep], sys.argv[sep + 1:]

    def read(p):
        return open(os.path.join(old_root, p.lstrip("/")), "rb").read()

    old = {}  # soname or basename -> path, for libraries in the old rootfs
    for d in ("lib", "usr/lib"):
        for f in os.listdir(os.path.join(old_root, d)):
            p = f"/{d}/{f}"
            full = os.path.join(old_root, d, f)
            if os.path.isfile(full) and ".so" in f:
                data = open(full, "rb").read()
                if data[:4] == b"\x7fELF":
                    old.setdefault(f, p)
                    so, _ = elf_dynamic(data)
                    if so:
                        old.setdefault(so, p)
    vendor, todo = set(roots), list(roots)
    stock_needed = {}  # soname -> set of vendor files needing it
    while todo:
        p = todo.pop()
        for n in elf_dynamic(read(p))[1]:
            lib = old.get(n)
            # a library under the same directory tree that is NOT a known stock name is vendor
            if lib and not any(n.startswith(s) for s in STOCK):
                if lib not in vendor:
                    vendor.add(lib)
                    todo.append(lib)
            else:
                stock_needed.setdefault(n, set()).add(p)

    new = new_libs(archives)
    new_by_soname = {}
    for n, data in new.items():
        so, _ = elf_dynamic(data)
        new_by_soname[so or n] = n
        new_by_soname.setdefault(n, n)
    exports_old = {so: elf_symbols(read(old[so]))[0] for so in stock_needed if so in old}
    exports_new = {n: elf_symbols(d)[0] for n, d in new.items()}

    print(f"vendor files checked: {len(vendor)}")
    for so in sorted(stock_needed):
        users = stock_needed[so]
        stem = so.split(".so")[0]
        same = new_by_soname.get(so)
        candidates = sorted({n for n in new_by_soname if n.split(".so")[0] == stem})
        target = same or (candidates[0] if candidates else None)
        wanted = set()
        for u in users:
            wanted |= elf_symbols(read(u))[1] & exports_old.get(so, set())
        missing = sorted(wanted - exports_new.get(new_by_soname.get(target, target), set())) if target else sorted(wanted)
        status = "same soname" if same else (f"RENAMED -> {', '.join(candidates)}" if candidates else "NOT IN NEW USERSPACE")
        print(f"\n{so}: {status}; {len(users)} vendor file(s), {len(wanted)} symbols used")
        if missing:
            print(f"  missing in new: {len(missing)}: {', '.join(missing[:25])}{' ...' if len(missing) > 25 else ''}")


# sonames that belong to stock OpenWrt / toolchain packages; anything else in the closure is vendor
STOCK = ("libc.so", "ld-musl", "libgcc_s", "libstdc++", "libubox", "libubus", "libuci", "libjson-c",
         "libblobmsg_json", "libnl-tiny", "libasound", "libpthread", "librt", "libm.so", "libdl", "libcrypto",
         "libssl", "libz.so", "libiwinfo", "liblua", "libuclient", "libsqlite3")

if __name__ == "__main__":
    main()
