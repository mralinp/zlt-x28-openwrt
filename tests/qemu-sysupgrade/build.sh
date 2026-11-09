#!/bin/bash
# Runs inside ubuntu:22.04 (arm64; Debian's kernel has no nandsim): builds a kernel+initramfs with nandsim, UBI and mtd-utils, then boots it in QEMU (TCG).
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq qemu-system-arm linux-image-generic mtd-utils busybox-static kmod xz-utils zstd cpio squashfs-tools file >/dev/null
K=$(ls /boot/vmlinuz-* | head -1 | sed 's#/boot/vmlinuz-##')
apt-get install -y -qq linux-modules-extra-$K >/dev/null
file -L /boot/vmlinuz-$K
R=/tmp/rd; rm -rf $R; mkdir -p $R/{bin,dev,proc,sys,tmp,lib,usr/sbin,x28}
cp /bin/busybox $R/bin/busybox; for a in sh cat dd cmp head tar sha256sum cut sed grep wc date cp rm mkdir ls od hexdump sleep printf echo insmod mount tr sort uname basename dirname env seq awk mv ln; do ln -sf busybox $R/bin/$a; done
copybin() { local b; b=$(command -v "$1"); mkdir -p $R$(dirname "$b"); cp "$b" $R$b; ldd "$b" | grep -o '/[^ ]*' | while read l; do mkdir -p $R$(dirname "$l"); cp -L "$l" $R$l; done; }
for t in ubiformat ubiattach ubidetach ubiblock ubinfo ubimkvol ubiupdatevol ubirmvol flash_erase nandwrite nanddump ubinize mksquashfs; do copybin $t; done
for l in $(find -L /usr/lib -name 'libgcc_s.so.1' | head -1); do mkdir -p $R$(dirname $l); cp -L $l $R$l; done
# modules: with their dependencies, decompressed
mods="nandsim ubi squashfs"
mkdir -p $R/mod; : > $R/mod/order
for m in $mods; do modprobe -S $K --show-depends $m 2>/dev/null | awk '/^insmod/{print $2}' ; done | awk '!s[$0]++' > /tmp/order
while read f; do b=$(basename $f); b=${b%.xz}; b=${b%.zst}; b=${b%.ko}; case $f in *.xz) xz -dc $f > $R/mod/$b.ko;; *.zst) zstd -dc $f > $R/mod/$b.ko;; *) cp $f $R/mod/$b.ko;; esac; echo $b >> $R/mod/order; done < /tmp/order
cp /x28/x28.sh /x28/test_guest.sh $R/x28/
cp /x28/init $R/init; chmod +x $R/init
(cd $R && find . | cpio -o -H newc 2>/dev/null | gzip -1 > /tmp/initrd.gz)
cp /boot/vmlinuz-$K /tmp/vmlinuz; if gzip -t /tmp/vmlinuz 2>/dev/null; then zcat /tmp/vmlinuz > /tmp/Image; mv /tmp/Image /tmp/vmlinuz; fi
echo "== booting"
timeout 900 qemu-system-aarch64 -M virt -cpu cortex-a57 -m 1536 -nographic -kernel /tmp/vmlinuz -initrd /tmp/initrd.gz -append "console=ttyAMA0 panic=-1 rdinit=/init" -no-reboot 2>&1 | tee /tmp/qemu.log | grep -a -E "^(x28|PASS|FAIL|\+\+|==)" || true
grep -a -q "^PASS-ALL" /tmp/qemu.log
