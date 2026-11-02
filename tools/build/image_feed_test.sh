#!/usr/bin/env bash
# #202: a management rootfs from first_boot.py, exactly as built, must use the public X28 feed with no setup. Needs network
# and an arm64 host; nothing runs on the router:
#
#   docker run --rm --cap-add MKNOD -v ROOTFS_DIR:/in:ro -v "$PWD/tools/build:/t:ro" debian:stable-slim bash /t/image_feed_test.sh
set -eu
R=/tmp/r
mkdir -p $R
tar -xzf /in/rootfs-management.tar.gz -C $R --exclude='./dev/*' 2>/dev/null
mkdir -p $R/dev $R/tmp/lock
rm -f $R/etc/resolv.conf
cp /etc/resolv.conf $R/etc/resolv.conf
mknod -m 666 $R/dev/null c 1 3
mknod -m 444 $R/dev/urandom c 1 9
cat > $R/t.sh <<'T'
set -eu
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
# Only our WireGuard module may be recorded; the stock kmod records are gone (#202).
test "$(ls /usr/lib/opkg/info | grep '^kmod-' | grep -vc '^kmod-wireguard\.')" = 0
test "$(opkg list-installed | grep '^kmod-' | grep -vc '^kmod-wireguard ')" = 0
opkg list-installed | grep -q '^kernel - 1:4.19.205-x28$'
opkg update >/tmp/u 2>&1 || { cat /tmp/u; exit 1; }
! grep -q 'Signature check failed' /tmp/u
test -s /var/opkg-lists/x28
test "$(opkg list-upgradable 2>/dev/null | grep -cE '^(kernel|kmod-)' || true)" = 0
opkg install ipset kmod-tun >/tmp/i 2>&1 || { cat /tmp/i; exit 1; }
opkg status ipset | grep -q '^Version: 1:7.17-1-x28-1$'
if opkg install kmod-nft-core >/dev/null 2>&1; then echo 'FAIL: kmod-nft-core installed'; exit 1; fi
opkg install tcpdump >/dev/null 2>&1
opkg install ppp-mod-pptp >/dev/null 2>&1 || { echo 'FAIL: ppp-mod-pptp'; exit 1; }
if [ -e /usr/lib/opkg/info/kmod-wireguard.control ]; then opkg list-installed | grep -q '^kmod-wireguard - 1:4.19.205-x28$'; opkg install wireguard-tools >/dev/null 2>&1; fi
opkg list-installed | grep -q '^kernel - 1:4.19.205-x28$'
echo 'IMAGE FEED PASS'
T
chroot $R /bin/sh /t.sh
