#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# x28-passthrough up/reapply/down with fake ip, iptables, uci and dnsmasq; no network changes.
set -u
here=$(cd "$(dirname "$0")/.." && pwd)
pt="$here/package/x28-mipc/files/x28-passthrough"
t=$(mktemp -d) || exit 1
trap 'rm -rf "$t"' EXIT
mkdir -p "$t/bin" "$t/run" "$t/sys/br-lan" "$t/dnsmasq.d"
echo 0 > "$t/sys/br-lan/proxy_arp"
# iptables keeps its rules as lines in a file: -C finds, -I adds, -D removes one.
cat > "$t/bin/iptables" <<'EOF'
#!/bin/sh
op=$3; shift 4; rule="$*"; f="$T/rules"; touch "$f"
case "$op" in
 -C) grep -qxF -- "$rule" "$f" ;;
 -I) echo "${rule#1 }" >> "$f" ;;
 -D) grep -qxF -- "$rule" "$f" || exit 1; grep -vxF -- "$rule" "$f" > "$f.n"; mv "$f.n" "$f" ;;
esac
EOF
cat > "$t/bin/ip" <<'EOF'
#!/bin/sh
echo "ip $*" >> "$T/calls"
case "$*" in "-4 route get 192.168.70."*) echo "$4 dev br-lan src 192.168.70.1" ;; "-4 route get "*) echo "$4 dev ccmni2 src 192.168.70.1" ;; esac
EOF
printf '#!/bin/sh\necho "uci $*" >> "$T/calls"; cat >> "$T/calls"\n' > "$t/bin/uci"
printf '#!/bin/sh\n:\n' > "$t/bin/logger"
printf '#!/bin/sh\n:\n' > "$t/bin/flock"
printf '#!/bin/sh\necho "dnsmasq $*" >> "$T/calls"\n' > "$t/bin/dnsmasq-init"
chmod 755 "$t/bin/"*
export T="$t" PATH="$t/bin:$PATH" X28_PT_RUN="$t/run" X28_PT_SYSCTL="$t/sys" X28_PT_LOCK="$t/lock" X28_PT_DNSMASQ="$t/bin/dnsmasq-init"
fail() { echo "FAIL: $*"; exit 1; }
conf="$t/dnsmasq.d/x28-passthrough.conf"
# pt_confdir looks in /tmp; point it at the test directory.
sed "s#/tmp/dnsmasq.d /tmp/dnsmasq.\*.d#$t/dnsmasq.d#" "$pt" > "$t/pt"

sh "$t/pt" up ccmni2 100.127.201.42 E8:DE:27:F6:DE:6F 10.0.0.53 || fail "up"
grep -qxF -- "-o ccmni2 -j SNAT --to-source 100.127.201.42 -m comment --comment x28-passthrough" "$t/rules" || fail "no SNAT"
grep -qxF -- "-i ccmni2 -d 100.127.201.42 -j ACCEPT -m comment --comment x28-passthrough" "$t/rules" || fail "no inbound accept"
grep -qF -- "--mac-source e8:de:27:f6:de:6f" "$t/rules" || fail "no MAC guard"
grep -qxF "ip -4 addr replace 100.127.201.43/32 dev br-lan" "$t/calls" || fail "no gateway on br-lan"
grep -qxF "ip -4 route replace 100.127.201.42/32 dev br-lan" "$t/calls" || fail "no host route"
[ "$(cat "$t/sys/br-lan/proxy_arp")" = 1 ] || fail "proxy_arp off"
grep -qxF "dhcp-range=set:x28-passthrough,100.127.201.42,static,255.255.255.248,10m" "$conf" || fail "no DHCP range"
grep -qxF "dhcp-option=tag:x28-passthrough,option:router,100.127.201.43" "$conf" || fail "no DHCP router"
grep -qxF "dhcp-option=tag:x28-passthrough,option:dns-server,10.0.0.53" "$conf" || fail "no DHCP DNS"
grep -qF "set firewall.x28_passthrough.path=/sbin/x28-passthrough" "$t/calls" || fail "no firewall include"
[ "$(grep -c '^dnsmasq restart' "$t/calls")" = 1 ] || fail "dnsmasq not restarted once"

# fw3 restart flushes the rules; the include puts them back once, without touching DHCP.
: > "$t/rules"
sh "$t/pt" && sh "$t/pt" || fail "reapply"
[ "$(wc -l < "$t/rules")" -eq 3 ] || fail "reapply did not restore exactly three rules"
[ "$(grep -c '^dnsmasq restart' "$t/calls")" = 1 ] || fail "reapply restarted dnsmasq"

# Same bearer again: no change. A new address: the old state is removed first.
sh "$t/pt" up ccmni2 100.127.201.42 e8:de:27:f6:de:6f 10.0.0.53 || fail "repeat up"
[ "$(grep -c '^dnsmasq restart' "$t/calls")" = 1 ] || fail "repeat up restarted dnsmasq"
sh "$t/pt" up ccmni3 10.9.8.47 e8:de:27:f6:de:6f || fail "new bearer"
grep -q "100.127.201.42" "$t/rules" && fail "old rules left"
grep -qxF "ip -4 addr del 100.127.201.43/32 dev br-lan" "$t/calls" || fail "old gateway left"
grep -qxF "dhcp-range=set:x28-passthrough,10.9.8.47,static,255.255.255.224,10m" "$conf" || fail "edge address not widened"
grep -q "dns-server" "$conf" && fail "DNS option without DNS"

sh "$t/pt" down || fail "down"
[ -s "$t/rules" ] && fail "rules left after down"
[ -e "$conf" ] && fail "DHCP snippet left after down"
[ -e "$t/run/x28-passthrough" ] && fail "state left after down"
[ "$(cat "$t/sys/br-lan/proxy_arp")" = 0 ] || fail "proxy_arp not restored"
sh "$t/pt" down || fail "second down"

# Refusals: a LAN address, a bad MAC, a bad device.
sh "$t/pt" up ccmni2 192.168.70.5 e8:de:27:f6:de:6f && fail "LAN address accepted"
sh "$t/pt" up ccmni2 100.127.201.42 e8:de:27:f6:de && fail "bad MAC accepted"
sh "$t/pt" up 'br-lan' 100.127.201.42 e8:de:27:f6:de:6f && fail "bad device accepted"
[ -e "$t/run/x28-passthrough" ] && fail "state left after a refusal"
sh "$pt" selftest >/dev/null || fail "selftest"
echo "PASS: x28-passthrough up, reapply after a firewall flush, bearer change, down and refusals"
