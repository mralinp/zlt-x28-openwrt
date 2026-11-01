#!/usr/bin/env bash
# Real opkg in a disposable arm64 container. Mount image archive /in and candidate /feed read-only.
# docker run --rm --cap-add MKNOD -v ROOTFS_DIR:/in:ro -v FEED_DIR:/feed:ro -v "$PWD/tools/build:/t:ro" debian:stable-slim bash /t/vendor_ipset_test.sh
set -eu
R=/tmp/r
mkdir -p "$R"
tar -xzf /in/rootfs-management.tar.gz -C "$R" --exclude='./dev/*'
mkdir -p "$R/feed" "$R/dev" "$R/tmp/lock"
cp /feed/* "$R/feed/"
rm -f "$R/etc/resolv.conf"
cp /etc/resolv.conf "$R/etc/resolv.conf"
mknod -m 666 "$R/dev/null" c 1 3
mknod -m 444 "$R/dev/urandom" c 1 9
awk 'BEGIN{RS="";ORS="\n\n"} !/Architecture: aarch64_cortex-a55/' "$R/usr/lib/opkg/status" > "$R/status"
mv "$R/status" "$R/usr/lib/opkg/status"
cat > "$R/test.sh" <<'TEST'
set -eu
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
usign -G -s /key.sec -p /key.pub
cp /key.pub "/etc/opkg/keys/$(usign -F -p /key.pub)"
usign -S -m /feed/Packages -s /key.sec -x /feed/good.sig
sed -i '/passwall/d' /etc/opkg/distfeeds.conf /etc/opkg/customfeeds.conf
echo 'src/gz x28 file:///feed' >> /etc/opkg/customfeeds.conf
grep -q '^option check_signature' /etc/opkg.conf
printf 'broken signature\n' > /feed/Packages.sig
opkg update >/tmp/bad-update 2>&1 || true
grep -q 'Signature check failed' /tmp/bad-update
test ! -s /var/opkg-lists/x28
echo 'PASS: invalid signature rejected before accepting local feed'
cp /feed/good.sig /feed/Packages.sig
opkg update >/tmp/update 2>&1
test -s /var/opkg-lists/x28
echo 'PASS: valid signed update accepted'
opkg install ipset >/tmp/install 2>&1 || { cat /tmp/install; exit 1; }
opkg status ipset | grep -q '^Version: 1:7.17-1-x28-1$'
opkg status x28-ipset-kernel | grep -q 'Status: install.*installed'
opkg status kernel | grep -q '^Version: 1:4.19.205-x28$'
opkg info x28-ipset-kernel | grep -q 'hash:ip,mac'
echo 'PASS: ipset installs with explicit vendor-subset dependency and limitation'
if opkg install kmod-ipt-ipset >/tmp/full-aggregate 2>&1; then
    echo 'FAIL: complete unsupported aggregate unexpectedly installed'; exit 1
fi
! opkg list-installed | grep -Eq '^kmod-.*5\.15'
test "$(find /lib/modules -newer /key.sec -type f | wc -l)" -eq 0
echo 'PASS: no complete aggregate or foreign module installed'
opkg remove ipset >/tmp/remove 2>&1
! opkg list-installed | grep -q '^ipset '
opkg install ipset >/tmp/reinstall 2>&1
opkg status ipset | grep -q '^Version: 1:7.17-1-x28-1$'
echo 'PASS: remove and reinstall preserve clean dependency resolution'
TEST
chroot "$R" /bin/sh /test.sh
