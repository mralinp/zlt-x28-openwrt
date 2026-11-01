#!/usr/bin/env bash
# Test the stub feed with the image's real opkg in a throwaway chroot, with the official feeds on (#200). Signs with a
# temporary key. Needs network. Runs on an arm64 host, nothing on the router:
#
#   docker run --rm --cap-add MKNOD -v ROOTFS_DIR:/in:ro -v FEED_DIR:/feed:ro -v "$PWD/tools/build:/t:ro" \
#     debian:stable-slim bash /t/opkg_feed_test.sh
#
# ROOTFS_DIR holds rootfs-management.tar.gz from stage_native.py / first_boot.py.
set -u
R=/tmp/r
mkdir -p $R
tar -xzf /in/rootfs-management.tar.gz -C $R --exclude='./dev/*' 2>/dev/null
mkdir -p $R/feed $R/dev $R/tmp/lock
cp /feed/* $R/feed/
rm -f $R/etc/resolv.conf
cp /etc/resolv.conf $R/etc/resolv.conf
mknod -m 666 $R/dev/null c 1 3
mknod -m 444 $R/dev/urandom c 1 9
# A unit's status has no foreign-arch stock records: opkg drops them on its first write (see #202).
awk 'BEGIN{RS="";ORS="\n\n"} !/Architecture: aarch64_cortex-a55/' $R/usr/lib/opkg/status > $R/s && mv $R/s $R/usr/lib/opkg/status

cat > $R/t.sh <<'EOF'
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
fails=0
check() { if [ "$2" = "$3" ]; then echo "ok    $1"; else echo "FAIL  $1: got '$2', want '$3'"; fails=$((fails+1)); fi; }
inst() { opkg list-installed | grep -c "^$1 "; }
try() { opkg install "$@" >/tmp/o 2>&1; echo $?; }

usign -G -s /k.sec -p /k.pub && cp /k.pub "/etc/opkg/keys/$(usign -F -p /k.pub)"
usign -S -m /feed/Packages -s /k.sec -x /feed/Packages.sig
sed -i '/passwall/d' /etc/opkg/distfeeds.conf /etc/opkg/customfeeds.conf
grep -q '^option check_signature' /etc/opkg.conf
check "signature checking is on" $? 0

opkg update >/dev/null 2>&1
check "without the feed, ipset fails" "$(try ipset)" 255

echo 'src/gz x28 file:///feed' >> /etc/opkg/customfeeds.conf
opkg update >/tmp/o 2>&1
check "feed update succeeds" $? 0
check "the feed's signature verifies" "$(grep -c 'Signature check failed' /tmp/o)" 0
check "opkg info prints no errors" "$(opkg info kmod-tun 2>&1 | grep -c 'ERROR')" 0
check "incomplete ipset dependency is refused" "$(try ipset)" 255
check "  ipset is not installed" "$(inst ipset)" 0
check "available tun stub installs" "$(try kmod-tun)" 0
check "  kernel" "$(inst kernel)" 1
check "  no incomplete ipset stub" "$(inst kmod-ipt-ipset)" 0
check "  no 5.15 kmod" "$(opkg list-installed | grep -E '^kmod-' | grep -c '5\.15')" 0
check "  stubs add no module files" "$(find /lib/modules -newer /k.sec -type f | wc -l)" 0
check "iptables-mod-iprange installs" "$(try iptables-mod-iprange)" 0
check "kmod-nft-core is refused" "$(try kmod-nft-core)" 255
check "  and not installed" "$(inst kmod-nft-core)" 0
check "iptables-mod-tproxy is refused" "$(try iptables-mod-tproxy)" 255
check "  and not installed" "$(inst kmod-ipt-tproxy)" 0
check "no 5.15 upgrade is offered" "$(opkg list-upgradable 2>/dev/null | grep -cE '^(kernel|kmod-)')" 0
check "userspace still installs" "$(try tcpdump)" 0
echo "failures: $fails"
exit $((fails > 0))
EOF
chroot $R /bin/sh /t.sh
