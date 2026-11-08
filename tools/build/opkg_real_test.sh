#!/usr/bin/env bash
# Test the whole feed (stubs, vendor ipset and the packages that carry our built modules) with the image's real opkg in a
# throwaway chroot, official feeds on (#396). Signs with a temporary key. Needs network. Runs on an arm64 host, nothing on
# the router. With -e FEED_URL=... it tests a published feed with the key the image ships instead (no /feed mount, no
# temporary key).
#
#   docker run --rm --cap-add MKNOD -v ROOTFS_DIR:/in:ro -v FEED_DIR:/feed:ro -v KMODS_DIR:/kmods:ro \
#     -v OLD_DIR:/old:ro -v "$PWD/package/x28-kmod-stubs/real.txt:/real.txt:ro" -v "$PWD/tools/build:/t:ro" \
#     debian:stable-slim bash /t/opkg_real_test.sh
#
# ROOTFS_DIR holds rootfs-management.tar.gz; FEED_DIR is the built feed; KMODS_DIR holds the built .ko files; OLD_DIR holds
# an older build of kmod-sched-core (version without -rN), as copied by hand to the test unit.
set -u
R=/tmp/r
mkdir -p $R
tar -xzf /in/rootfs-management.tar.gz -C $R --exclude='./dev/*' 2>/dev/null
mkdir -p $R/feed $R/dev $R/tmp/lock $R/kmods $R/old
cp /feed/* $R/feed/
cp /kmods/*.ko $R/kmods/
cp /old/*.ipk $R/old/
cp /real.txt $R/real.txt
rm -f $R/etc/resolv.conf
cp /etc/resolv.conf $R/etc/resolv.conf
mknod -m 666 $R/dev/null c 1 3
mknod -m 444 $R/dev/urandom c 1 9
awk 'BEGIN{RS="";ORS="\n\n"} !/Architecture: aarch64_cortex-a55/' $R/usr/lib/opkg/status > $R/s && mv $R/s $R/usr/lib/opkg/status

cat > $R/t.sh <<'EOF'
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
fails=0
check() { if [ "$2" = "$3" ]; then echo "ok    $1"; else echo "FAIL  $1: got '$2', want '$3'"; fails=$((fails+1)); fi; }
inst() { opkg list-installed | grep -c "^$1 "; }
try() { opkg install "$@" >/tmp/o 2>&1 </dev/null; echo $?; }

sed -i '/passwall/d' /etc/opkg/distfeeds.conf /etc/opkg/customfeeds.conf
# The image already has an x28 line (feed-2); a second one with the same name is skipped, so replace it.
sed -i '/^src\/gz x28 /d' /etc/opkg/customfeeds.conf
if [ -n "${FEED_URL:-}" ]; then
	# Live feed: the key the image ships must be the one that signed it, so no temporary key.
	echo "src/gz x28 $FEED_URL" >> /etc/opkg/customfeeds.conf
	check "the image ships the feed key" "$(ls /etc/opkg/keys | grep -c '^7fec994ab0d15b97$')" 1
else
	usign -G -s /k.sec -p /k.pub && cp /k.pub "/etc/opkg/keys/$(usign -F -p /k.pub)"
	usign -S -m /feed/Packages -s /k.sec -x /feed/Packages.sig
	echo 'src/gz x28 file:///feed' >> /etc/opkg/customfeeds.conf
fi
grep -c '^src/gz x28 ' /etc/opkg/customfeeds.conf /etc/opkg/distfeeds.conf | tr '\n' ' '; echo
opkg update >/tmp/o 2>&1
check "feed update succeeds" $? 0
check "the feed's signature verifies" "$(grep -c 'Signature check failed' /tmp/o)" 0
check "the index lists 209 packages" "$(zcat /var/opkg-lists/x28 | grep -c '^Package:')" 209

echo "--- each package that carries our modules"
while read -r line; do
	case "$line" in ''|'#'*) continue ;; esac
	names=${line%%|*}; set -- $names; pkg=$1; shift
	check "$pkg installs" "$(try $pkg)" 0
	check "  is the -r build" "$(opkg list-installed $pkg | grep -c ' - 1:4.19.205-x28-r[0-9]*$')" 1
	for m in "$@"; do
		check "  $m.ko is the built file" "$(cmp -s /lib/modules/x28/$m.ko /kmods/$m.ko && echo same || echo different)" same
	done
	[ $# -eq 0 ] && check "  carries no files" "$(opkg files $pkg | tail -n +2 | grep -c .)" 0
done < /real.txt
check "no 5.15 kmod is installed" "$(opkg list-installed | grep -E '^kmod-' | grep -c '5\.15')" 0
check "no 5.15 upgrade is offered" "$(opkg list-upgradable 2>/dev/null | grep -cE '^(kernel|kmod-)')" 0

echo "--- real consumers from the official feed"
for p in tc-full sqm-scripts ss iptables-mod-hashlimit iptables-mod-ipsec nbd usbip proto-bonding; do
	check "$p installs" "$(try $p)" 0
done

echo "--- still refused"
check "kmod-nft-core is refused" "$(try kmod-nft-core)" 255
check "iptables-mod-quota2 is refused" "$(try iptables-mod-quota2)" 255
check "open-iscsi is refused" "$(try open-iscsi)" 255
check "kmod-ipt-ipset (incomplete) is refused" "$(try kmod-ipt-ipset)" 255
check "ipset installs through the vendor subset" "$(try ipset)" 0

echo "--- upgrade from the hand-copied build"
opkg remove kmod-sched-bpf kmod-sched-cake kmod-sched-act-vlan kmod-sched-flower tc-full sqm-scripts >/dev/null 2>&1
opkg remove --force-depends kmod-sched-core >/dev/null 2>&1
check "old kmod-sched-core installs" "$(try /old/kmod-sched-core_4.19.205-x28_aarch64_generic.ipk)" 0
check "  at the plain version" "$(opkg list-installed kmod-sched-core | grep -c ' - 1:4.19.205-x28$')" 1
opkg update >/dev/null 2>&1
check "  it is offered as an upgrade" "$(opkg list-upgradable 2>/dev/null | grep -c '^kmod-sched-core ')" 1
check "  upgrade succeeds" "$(opkg upgrade kmod-sched-core >/tmp/o 2>&1; echo $?)" 0
check "  now the -r build" "$(opkg list-installed kmod-sched-core | grep -c ' - 1:4.19.205-x28-r[0-9]*$')" 1
echo "failures: $fails"
exit $((fails > 0))
EOF
chroot $R /bin/sh /t.sh
