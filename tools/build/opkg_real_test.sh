#!/usr/bin/env bash
# Test the whole feed (stubs, vendor ipset and the packages that carry our built modules) with the image's real opkg in a
# throwaway chroot, official feeds on (#396). Signs with a temporary key. Needs network. Runs on an arm64 host, nothing on
# the router. With -e EXPECT_PACKAGES=N it also checks the size of the index. With -e FEED_URL=... it tests a published feed with the key the image ships instead (no /feed mount, no
# temporary key).
#
#   docker run --rm --cap-add MKNOD -v ROOTFS_DIR:/in:ro -v FEED_DIR:/feed:ro -v KMODS_DIR:/kmods:ro \
#     -v OLD_DIR:/old:ro -v "$PWD/package/x28-kmod-stubs/real.txt:/real.txt:ro" \
#     -v "$PWD/package/x28-kmods/files/x28-kmods.init:/loader.init:ro" -v "$PWD/package:/pkg:ro" -v "$PWD/tools/build:/t:ro" \
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
[ -f /loader.init ] && cp /loader.init $R/loader.init
[ -d /pkg ] && cp -R /pkg $R/pkg
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
# opkg exits 0 after printing `wfopen: ... No such file or directory`, so errors in its output count too; the one benign
# messages (pkg_hash_*: opkg weighing the official 5.15 records it ignores; the install still completes) are filtered.
# A download that fails ("Check your network settings") is retried up to 5 times: the live URL is a CDN reached through the image's own fetcher.
try() { for attempt in 1 2 3 4 5; do opkg install "$@" >/tmp/o 2>&1 </dev/null; rc=$?; grep -q 'opkg_download\|Failed to download' /tmp/o || break; sleep 4; done; [ $rc -eq 0 ] && [ "$(grep '^ \* ' /tmp/o | grep -vc 'pkg_hash_')" -gt 0 ] && rc=254; echo $rc; }

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
for attempt in 1 2 3 4 5; do opkg update >/tmp/o 2>&1; rc=$?; [ $rc -eq 0 ] && break; sleep 4; done
check "feed update succeeds" $rc 0
check "the feed's signature verifies" "$(grep -c 'Signature check failed' /tmp/o)" 0
[ -z "${EXPECT_PACKAGES:-}" ] || check "the index lists $EXPECT_PACKAGES packages" "$(zcat /var/opkg-lists/x28 | grep -c '^Package:')" "$EXPECT_PACKAGES"

echo "--- the records an older image invents for its baked modules (replaced by the feed packages below)"
for p in kmod-wireguard kmod-ipt-tproxy kmod-ipt-socket; do echo "info  $p before: $(opkg list-installed $p | cut -d' ' -f3)"; done
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

echo "--- the loader as a package (#416)"
echo "info  the image's loader before: $(opkg status x28-kmods | grep -c Package) record(s), script $(wc -c < /etc/init.d/x28-kmods) bytes, enabled=$(ls /etc/rc.d/S97x28-kmods 2>/dev/null | wc -l)"
check "x28-kmods installs over the image's unowned script" "$(try x28-kmods)" 0
check "  is the -r build" "$(opkg list-installed x28-kmods | grep -c ' - 1:4.19.205-x28-r[0-9]*$')" 1
check "  owns the init script" "$(opkg files x28-kmods | grep -c '^/etc/init.d/x28-kmods$')" 1
check "  the script is the one in the repo" "$(cmp -s /etc/init.d/x28-kmods /loader.init && echo same || echo different)" same
check "  is enabled at boot (S97 link)" "$(ls /etc/rc.d/S97x28-kmods 2>/dev/null | wc -l)" 1
/etc/init.d/x28-kmods modules > /tmp/mods 2>/tmp/modserr
check "  'modules' lists every module of the installed packages once" "$(wc -l < /tmp/mods)" "$(cat /etc/x28-kmods.d/* | sort -u | grep -c .)"
check "  no module is listed twice" "$(sort /tmp/mods | uniq -d | wc -l)" 0
check "  x28_udp_lookup comes before nf_socket_ipv4" "$(awk '/^x28_udp_lookup$/{a=NR} /^nf_socket_ipv4$/{b=NR} END{print (a>0 && b>a)}' /tmp/mods)" 1
check "  libchacha comes before chacha20poly1305" "$(awk '/^libchacha$/{a=NR} /^chacha20poly1305$/{b=NR} END{print (a>0 && b>a)}' /tmp/mods)" 1
check "  kmod-ipt-tproxy's list sorts before kmod-ipt-socket's" "$(ls /etc/x28-kmods.d | awk '/-kmod-ipt-tproxy$/{a=NR} /-kmod-ipt-socket$/{b=NR} END{print (a>0 && b>a)}')" 1
echo "info  $(wc -l < /tmp/mods) modules in the load order, $(ls /etc/x28-kmods.d | wc -l) list files"
check "removing a module package removes its list file" "$(opkg remove kmod-nbd >/dev/null 2>&1; ls /etc/x28-kmods.d | grep -c nbd)" 0
check "  and its module from the load" "$(/etc/init.d/x28-kmods modules | grep -c '^nbd$')" 0
check "  reinstalling brings it back" "$(try kmod-nbd >/dev/null; /etc/init.d/x28-kmods modules | grep -c '^nbd$')" 1
check "removing the loader removes the boot link" "$(opkg remove x28-kmods >/dev/null 2>&1; ls /etc/rc.d/S97x28-kmods 2>/dev/null | wc -l)" 0
check "  and the script" "$([ -e /etc/init.d/x28-kmods ] && echo present || echo gone)" gone
check "reinstalling the loader enables it again" "$(try x28-kmods >/dev/null; ls /etc/rc.d/S97x28-kmods 2>/dev/null | wc -l)" 1
echo "--- the x28-* packages (#417)"
if [ -f /pkg/x28-packages.ini ]; then
	awk '/^\[/{gsub(/[][]/,""); pkg=$0} /^[ \t]+[0-7][0-7][0-7][0-7] \//{print pkg, $1, $2, $3}' /pkg/x28-packages.ini > /tmp/x28files
	for p in $(awk '{print $1}' /tmp/x28files | uniq); do
		check "$p installs" "$(try $p)" 0
		check "  is version 0.1.0-1" "$(opkg list-installed $p | grep -c ' - 0\.1\.0-1$')" 1
		while read -r _ mode dest src; do
			check "  $dest is the source file" "$(cmp -s /pkg/$src $dest && echo same || echo different)" same
			case $mode in 0755) want=rwxr-xr-x ;; 0644) want=rw-r--r-- ;; *) want=$mode ;; esac  # busybox has no stat
			check "  $dest has mode $mode" "$(ls -l $dest | cut -c2-10)" "$want"
			case $dest in /etc/init.d/*) n=${dest##*/}; check "  $n is enabled at boot" "$(ls /etc/rc.d/S??$n 2>/dev/null | wc -l)" 1 ;; esac
		done <<EOT
$(grep "^$p " /tmp/x28files)
EOT
	done
	check "removing x28-leds removes its files and boot link" "$(opkg remove x28-leds >/dev/null 2>&1; ls /sbin/x28-leds /etc/init.d/x28-leds /etc/rc.d/S??x28-leds 2>/dev/null | wc -l)" 0
	check "  reinstalling brings them and the link back" "$(try x28-leds >/dev/null; ls /sbin/x28-leds /etc/init.d/x28-leds /etc/rc.d/S??x28-leds 2>/dev/null | wc -l)" 3
	check "removing x28-wifi removes both boot links" "$(opkg remove x28-wifi >/dev/null 2>&1; ls /etc/rc.d/S??x28-wps /etc/rc.d/S??x28-wifi-l1 /etc/init.d/x28-wps 2>/dev/null | wc -l)" 0
	check "  reinstalling brings them back" "$(try x28-wifi >/dev/null; ls /etc/rc.d/S??x28-wps /etc/rc.d/S??x28-wifi-l1 /etc/init.d/x28-wps 2>/dev/null | wc -l)" 3
	check "removing x28-mipc is refused while x28-modem needs it" "$(opkg remove x28-mipc >/dev/null 2>&1; echo $?)" 255
else
	echo "info  /pkg not mounted; skipping"
fi
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
