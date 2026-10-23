#!/bin/sh
# Run the 23.05 userspace we build on the X28 itself, in RAM, on the stock 4.19 kernel.
#   ssh router 'cat > /tmp/x28-rootfs.tar.gz' < private/build/out/openwrt-23.05.5-armsr-armv8-generic-rootfs.tar.gz
#   ssh router 'sh -s' < tools/build/device_ram_test.sh
# The stock kernel has no kexec and no net/pid namespaces, so this is a chroot in tmpfs that shares the
# live network stack: netifd, "firewall restart" and dnsmasq are NOT run (they would take over the router).
# fw3 is checked with "print" only, which writes the rules to stdout and applies nothing.
# Writes only under /tmp; starts ubusd/rpcd/uhttpd (127.0.0.1 only) and stops exactly those on exit.

R=/tmp/x28-ramtest
TAR=/tmp/x28-rootfs.tar.gz
PORT=8099
PIDS=

cleanup() {
	trap '' INT TERM HUP PIPE
	# only PIDs still rooted in the chroot: a daemon that died early may have had its PID reused by the host
	for p in $PIDS; do [ "$(readlink /proc/$p/root)" = "$R" ] && kill "$p" 2>/dev/null; done
	sleep 2
	umount "$R/proc" 2>/dev/null; umount "$R/dev" 2>/dev/null
	if grep -q " $R/" /proc/mounts; then
		echo "WARNING: still mounted under $R, NOT deleting it:"; grep " $R/" /proc/mounts
	else
		rm -rf "$R"
	fi
	rm -f "$TAR"
}

[ -f "$TAR" ] || { echo "missing $TAR"; exit 2; }
[ -e "$R" ] && { echo "$R exists (earlier run?); inspect /proc/mounts and remove it by hand"; exit 2; }
avail=$(awk '/^MemAvailable/ {print int($2/1024)}' /proc/meminfo)
temp=$(($(cat /sys/class/thermal/thermal_zone0/temp) / 1000))
[ "$avail" -ge 100 ] || { echo "only ${avail} MB available"; exit 2; }
[ "$temp" -le 80 ] || { echo "SoC at ${temp} C"; exit 2; }
netstat -ltn | grep -q ":$PORT " && { echo "port $PORT in use"; exit 2; }
echo "start: ${avail} MB available, SoC ${temp} C"

trap cleanup EXIT
trap 'exit 1' INT TERM HUP PIPE  # PIPE: a dropped ssh shows up as a failed write, not SIGHUP
mkdir -p "$R" && tar xzf "$TAR" -C "$R" || exit 1
mkdir -p "$R/proc" "$R/dev" "$R/tmp/run/ubus"
mount -t proc proc "$R/proc"
mount -t tmpfs -o size=64k,mode=755 dev "$R/dev"  # private /dev, not a bind of the host's
mknod -m 666 "$R/dev/null" c 1 3; mknod -m 666 "$R/dev/zero" c 1 5
mknod -m 666 "$R/dev/random" c 1 8; mknod -m 666 "$R/dev/urandom" c 1 9

mkdir -p "$R/run"  # iptables' /run/xtables.lock
# </dev/null: under "sh -s" stdin is this script, a reading child would eat the rest of it
C() { chroot "$R" /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin "$@" </dev/null; }
# a plain command, not the C function: $! must be the daemon itself (chroot and env exec), not a subshell
bg() { chroot "$R" /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin "$@" </dev/null >/dev/null 2>&1 & PIDS="$PIDS $!"; }
pass=0 fail=0
check() {  # name, regex the output must match, command...
	name=$1 want=$2; shift 2
	out=$("$@" 2>&1); rc=$?
	if [ $rc -eq 0 ] && printf '%s\n' "$out" | grep -qE "$want"; then r=PASS pass=$((pass + 1)); else r=FAIL fail=$((fail + 1)); fi
	printf '%s  %-20s %s\n' $r "$name" "$(printf '%s\n' "$out" | grep -E -m1 "$want" || printf '%s' "rc=$rc $out" | head -c 120)"
}

check "musl on 4.19"       '^ok$'          C /bin/sh -c 'echo ok'
check "release"            "23\.05\.5"     C /bin/sh -c '. /etc/openwrt_release; echo $DISTRIB_RELEASE'
check "uci"                'zone'          C uci show firewall
check "no fw4/nftables"    '^none$'        C /bin/sh -c 'opkg list-installed | grep -E "^(firewall4|nftables|kmod-nft)" || echo none'
check "iptables backend"   'legacy'        C iptables -V
check "iptables reads live" '^-P INPUT'    C iptables -S INPUT

# procd can't be init in a chroot, but LuCI's header needs its "system board"; stand in with an rpcd plugin
mkdir -p "$R/usr/libexec/rpcd"
cat > "$R/usr/libexec/rpcd/system" <<'EOF'
#!/bin/sh
case "$1" in
list) echo '{ "board": {} }' ;;
call) echo '{ "hostname": "x28-ramtest", "rootfs_type": "tmpfs", "release": { "distribution": "OpenWrt" } }' ;;
esac
EOF
chmod +x "$R/usr/libexec/rpcd/system"
# the image's root has an empty password; a login would give rpcd rc/rpc-sys/file exec, which act on the live host
sed -i 's/^root::/root:*:/' "$R/etc/shadow"
bg ubusd
i=0; while [ ! -S "$R/tmp/run/ubus/ubus.sock" ] && [ $i -lt 10 ]; do sleep 1; i=$((i + 1)); done
bg rpcd
sleep 2
check "ubus/rpcd"          'session'       C ubus list
check "rpcd uci"           'firewall'      C ubus call uci configs

# print only: its output is iptables commands, running them would replace the live firewall
check "fw3 print"          'zone_lan'      C fw3 -4 print

bg uhttpd -f -p 127.0.0.1:$PORT -h /www -x /cgi-bin  # no -u /ubus: the login page doesn't need it
i=0; while ! netstat -ltn | grep -q "127.0.0.1:$PORT " && [ $i -lt 10 ]; do sleep 1; i=$((i + 1)); done
# LuCI answers its login page with HTTP 403; check the code and the page title
check "LuCI login page"    '^(200|403) .*LuCI' /bin/sh -c "curl -s -m 30 -w '\n%{http_code}' http://127.0.0.1:$PORT/cgi-bin/luci/ </dev/null | awk '/<title>/ {t=\$0} END {print \$0, t}'"

temp=$(($(cat /sys/class/thermal/thermal_zone0/temp) / 1000))
echo "end: SoC ${temp} C"
echo "RESULT: $pass/$((pass + fail)) checks passed"
[ $fail -eq 0 ]
