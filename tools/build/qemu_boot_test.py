#!/usr/bin/env python3
"""Boot an OpenWrt armsr/armv8 build in QEMU and check the userspace actually works.

Boots kernel + ext4 rootfs on a virtual arm64 machine (`virt`, Cortex-A53) over a serial console,
then checks: procd is init, netifd brings up br-lan, the fw3 firewall loads its ruleset with
iptables-legacy (and no nftables), rpcd/ubus answer, and LuCI is served over HTTP (from inside
the VM and through a forwarded port). This tests OUR userspace and configuration on the matching
23.05 kernel, not the X28's 4.19 kernel.

Needs qemu-system-aarch64. On an Apple Silicon Mac, in Docker (arm64 Linux, TCG emulation):

    docker run --rm -v "$PWD/tools/build:/t:ro" -v "$PWD/private/build/out:/img:ro" debian:bookworm-slim \
      bash -c 'apt-get update -qq && apt-get install -y -qq qemu-system-arm curl >/dev/null && \
               python3 /t/qemu_boot_test.py /img/openwrt-23.05.5-armsr-armv8-generic-kernel.bin \
                                            /img/openwrt-23.05.5-armsr-armv8-generic-ext4-rootfs.img.gz'
"""
import gzip
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time

PROMPT = "root@OpenWrt:"
CHECKS = [  # (name, command, regex that must match the output)
    ("release", "cat /etc/openwrt_release | grep -E 'RELEASE|TARGET'", r"23\.05"),
    ("kernel", "uname -r", r"\d+\.\d+"),
    ("init is procd", "cat /proc/1/comm", r"procd"),
    ("netifd lan up", "ifstatus lan | jsonfilter -e '@.up'", r"true"),
    ("br-lan address", "ip -4 addr show br-lan | grep -o 'inet [0-9./]*'", r"192\.168\.1\.1/24"),
    ("firewall restart", "/etc/init.d/firewall restart 2>&1; echo rc=$?", r"rc=0"),
    ("fw3 chains", "iptables -S | grep -c -E 'zone_(lan|wan)'", r"^[1-9]\d*$"),
    ("iptables backend", "iptables -V", r"legacy"),
    ("no nftables", "ls /usr/sbin/nft /usr/sbin/fw4 2>&1 | grep -c 'No such'", r"^2$"),
    ("ubus/rpcd", "ubus call system board | jsonfilter -e '@.release.version'", r"23\.05"),
    ("uhttpd running", "pgrep uhttpd >/dev/null && echo up", r"up"),
    # LuCI itself is checked from outside the VM (below): uclient-fetch drops the body on HTTP 403
]
DIAG = [  # printed, not judged: helps explain a failure
    "uci show uhttpd.main | grep -E 'listen|rfc1918|home'",
    "logread | grep -iE 'uhttpd|luci|firewall' | tail -5",
]


class Console:
    def __init__(self, proc):
        self.p, self.buf, self.log = proc, "", []

    def read_until(self, pattern, timeout):
        end = time.time() + timeout
        while time.time() < end:
            if re.search(pattern, self.buf):
                return True
            r, _, _ = select.select([self.p.stdout], [], [], 0.5)
            if r:
                chunk = os.read(self.p.stdout.fileno(), 4096).decode(errors="replace")
                if not chunk:  # EOF: QEMU exited (select keeps reporting a closed pipe as readable)
                    sys.exit(f"QEMU exited with {self.p.wait()}:\n{''.join(self.log)[-2000:]}")
                self.buf += chunk
                self.log.append(chunk)
        return False

    def run(self, cmd, timeout=60):
        """Run a shell command; terminal echo is off, and the marker is split in the command text
        so only the real output can match it."""
        self.buf = ""
        tag = str(int(time.time() * 1000))
        self.p.stdin.write(f'{cmd}; echo "__E""ND_{tag}__"\n'.encode())
        self.p.stdin.flush()
        self.read_until(rf"__END_{tag}__", timeout)
        return self.buf.split(f"__END_{tag}__")[0].replace("\r", "").strip()


def main():
    kernel, rootfs = sys.argv[1], sys.argv[2]
    work = tempfile.mkdtemp()
    img = os.path.join(work, "rootfs.img")
    with (gzip.open(rootfs) if rootfs.endswith(".gz") else open(rootfs, "rb")) as src, open(img, "wb") as dst:
        shutil.copyfileobj(src, dst)
    cmd = ["qemu-system-aarch64", "-M", "virt", "-cpu", "cortex-a53", "-smp", "2", "-m", "512", "-nographic",
           "-kernel", kernel, "-append", "root=/dev/vda rootwait console=ttyAMA0",
           "-drive", f"file={img},format=raw,if=virtio",
           "-netdev", "user,id=lan,net=192.168.1.0/24,host=192.168.1.2,hostfwd=tcp:127.0.0.1:8080-192.168.1.1:80",
           "-device", "virtio-net-pci,netdev=lan,romfile="]  # no PXE ROM needed for a direct kernel boot
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    con, t0 = Console(proc), time.time()
    failures = 0
    try:
        print("QEMU started; booting (software-emulated CPU, about 1 min)...", flush=True)
        if not con.read_until(r"Please press Enter to activate this console", 600):
            print("".join(con.log)[-3000:])
            sys.exit("boot did not reach the console prompt")
        print(f"booted to console in {time.time() - t0:.0f} s")
        time.sleep(20)  # let netifd, firewall and uhttpd settle after procd's boot
        proc.stdin.write(b"\n")
        proc.stdin.flush()
        con.read_until(PROMPT, 60)
        con.run("stty -echo")
        for name, command, expect in CHECKS:
            out = con.run(command)
            ok = re.search(expect, out, re.M) is not None
            failures += not ok
            print(f"{'PASS' if ok else 'FAIL'}  {name:<18} {out.splitlines()[-1] if out else '(no output)'}"[:160])
        http = subprocess.run(["curl", "-s", "-m", "20", "-w", "\n%{http_code}", "http://127.0.0.1:8080/cgi-bin/luci/"],
                              capture_output=True, text=True)
        body, _, code = http.stdout.rpartition("\n")
        ok = code in ("200", "403") and "<title>OpenWrt - LuCI</title>" in body  # 403 = LuCI's login page
        failures += not ok
        snippet = "" if ok else re.sub(r"\s+", " ", body)[:100]
        print(f"{'PASS' if ok else 'FAIL'}  {'LuCI via hostfwd':<18} HTTP {code} {snippet}")
        for command in DIAG:
            print(f"  diag: {command}\n    " + con.run(command).replace("\n", "\n    "))
    finally:
        proc.kill()
        shutil.rmtree(work)
    print(f"RESULT: {len(CHECKS) + 1 - failures}/{len(CHECKS) + 1} checks passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
