#!/usr/bin/env python3
"""Link-test vendor binaries from the stock rootfs on a new OpenWrt userspace, with musl's own loader.

Unpacks the new userspace rootfs (and extra .ipk packages) into a scratch tree, copies in the
given vendor binaries plus every library they need that the new tree lacks BY EXACT NAME (that is
exactly the vendor libraries and the 19.07 compatibility libraries), then runs
`chroot TREE /lib/ld-musl-aarch64.so.1 --list BIN` for each. musl resolves every library and
performs all relocations in --list mode, so missing libraries or symbols fail here; the vendor
programs themselves are never executed.

Needs root (chroot) on an arm64 Linux host. On an Apple Silicon Mac, Docker's default arm64 Linux:

    docker run --rm --network none -v x28-rootfs-b-analysis-20261021:/r:ro \
      -v "$PWD/tools:/tools:ro" -v "$PWD/private:/p:ro" x28-firmware-tools:local \
      python3 /tools/build/link_check.py --old-rootfs /r/rootfs \
        --userspace /p/build/release-v0.1.0/x28-userspace-v0.1.0-openwrt-23.05.5-armsr-armv8-rootfs.tar.gz \
        --ipk /p/third-party/openwrt-23.05.5/dl/*.ipk

The scratch tree holds proprietary files: it lives in /tmp inside the container and is discarded.
"""
import argparse
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "firmware"))
from inventory import elf_dynamic  # noqa: E402

DEFAULT_BINS = ["/usr/bin/nvram_daemon", "/usr/bin/ccci_fsd", "/usr/bin/ccci_mdinit", "/usr/bin/mtk_netagent",
                "/usr/bin/mipc_wan_cli", "/usr/bin/ql_netd", "/usr/bin/ql_ril_service", "/usr/bin/mipc_submonitor",
                "/usr/bin/hwnat", "/usr/bin/switch"]


def extract(tf, dest):
    tf.extractall(dest, filter="tar") if hasattr(tarfile, "data_filter") else tf.extractall(dest)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--old-rootfs", required=True, help="extracted stock rootfs (case-sensitive filesystem)")
    ap.add_argument("--userspace", required=True, help="new userspace rootfs .tar.gz")
    ap.add_argument("--ipk", nargs="*", default=[], help="extra packages to install first (e.g. libstdcpp6)")
    ap.add_argument("--bin", nargs="*", default=DEFAULT_BINS, help="vendor binaries to test")
    args = ap.parse_args()
    old = args.old_rootfs.rstrip("/")
    new = tempfile.mkdtemp(prefix="x28-link-")

    extract(tarfile.open(args.userspace), new)
    for ipk in args.ipk:
        outer = tarfile.open(ipk)
        data = outer.extractfile(next(m for m in outer.getmembers() if m.name.endswith("data.tar.gz"))).read()
        extract(tarfile.open(fileobj=io.BytesIO(data)), new)

    def in_new(name):
        return any(os.path.lexists(f"{new}{d}/{name}") for d in ("/lib", "/usr/lib"))

    def in_old(name):
        return next((f"{d}/{name}" for d in ("/lib", "/usr/lib") if os.path.lexists(f"{old}{d}/{name}")), None)

    copied, todo, seen, unresolved = [], list(args.bin), set(), []
    while todo:
        p = todo.pop()
        if p in seen:
            continue
        seen.add(p)
        real = os.path.realpath(old + p)
        os.makedirs(os.path.dirname(new + p), exist_ok=True)
        if not os.path.lexists(new + p):
            shutil.copy2(real, new + p)
            copied.append(p)
        for n in elf_dynamic(open(real, "rb").read())[1]:
            if not in_new(n):
                (todo.append(in_old(n)) if in_old(n) else unresolved.append(n))
    print("copied from the stock rootfs:", " ".join(sorted(copied)))
    if unresolved:
        print("needed but found nowhere:", " ".join(sorted(set(unresolved))))

    failed = 0
    for b in args.bin:
        res = subprocess.run(["chroot", new, "/lib/ld-musl-aarch64.so.1", "--list", b],
                             capture_output=True, text=True, timeout=60)
        out = res.stdout + res.stderr
        errors = [l for l in out.splitlines() if "rror" in l or "not found" in l]
        libs = [l.split()[0] for l in res.stdout.splitlines() if "=>" in l]
        ok = res.returncode == 0 and not errors
        failed += not ok
        print(f"{b:<26} {'OK  ' if ok else 'FAIL'} {len(libs):>2} libraries: {' '.join(libs)}")
        for e in errors[:8]:
            print("    ", e)
    shutil.rmtree(new)
    print(f"RESULT: {len(args.bin) - failed}/{len(args.bin)} resolved")
    sys.exit(1 if failed or unresolved else 0)


if __name__ == "__main__":
    main()
