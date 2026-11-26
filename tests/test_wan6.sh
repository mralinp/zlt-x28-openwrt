#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# wan + wan6 on the cellular WAN (#648): x28_mipc publishes the bearer's IPv6 for an x28_mipc6 interface on '@wan' and stops
# reporting it itself; x28_mipc6 installs it. netifd, uci and the proto helpers are replaced by recorders.
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
calls=$t/calls; X28_MIPC_RUN=$t/run; X28_MIPC6_WAIT=0; export X28_MIPC_RUN X28_MIPC6_WAIT
fail() { echo "FAIL: $*" >&2; exit 1; }
# Config the fake uci answers from: "<section> <proto> <device>" per interface.
cfg=$t/cfg
uci() {
	[ "$1" = -q ] && shift
	case "$1" in
	show) while read -r s p d x y; do echo "network.$s=interface"; echo "network.$s.proto='$p'"; done < "$cfg" ;;
	get) k=${2#network.}; s=${k%%.*}; o=${k#*.}
		while read -r sec p d x y; do [ "$sec" = "$s" ] && { [ "$o" = proto ] && echo "$p"; [ "$o" = device ] && echo "$d"; [ "$o" = disabled ] && [ "$x" != - ] && echo "$x"; [ "$o" = auto ] && [ "$y" != - ] && echo "$y"; }; done < "$cfg"; : ;;
	esac
}
for f in proto_init_update proto_add_ipv4_address proto_add_ipv4_route proto_add_dns_server proto_add_ipv6_address proto_add_ipv6_prefix \
	proto_add_ipv6_route proto_add_data json_add_int json_add_string proto_close_data proto_send_update proto_notify_error proto_block_restart; do
	eval "$f() { echo \"$f \$*\" >> \"$calls\"; }"
done
json_get_vars() { for v in "$@"; do eval "$v=\${t_$v-}"; done; }  # options come from t_<name>
INCLUDE_ONLY=1 . "$root/package/x28-mipc/files/x28_mipc.sh"
INCLUDE_ONLY=1 . "$root/package/x28-mipc/files/x28_mipc6.sh"

printf 'lan static -\nwan x28_mipc -\n' > "$cfg"
x28_mipc_has_wan6 wan && fail 'no wan6 configured, but one was found'
printf 'lan static -\nwan x28_mipc -\nwan6 x28_mipc6 @wan\n' > "$cfg"
x28_mipc_has_wan6 wan || fail 'wan6 on @wan not found'
x28_mipc_has_wan6 wwan2 && fail 'wan6 matched another interface'
printf 'wan6 dhcpv6 @wan\n' > "$cfg"
x28_mipc_has_wan6 wan && fail 'a dhcpv6 wan6 is not ours'
# A wan6 that cannot run (disabled, not auto) must not make wan drop its IPv6.
printf 'wan6 x28_mipc6 @wan 1 -\n' > "$cfg"; x28_mipc_has_wan6 wan && fail 'a disabled wan6 counts'
printf 'wan6 x28_mipc6 @wan - 0\n' > "$cfg"; x28_mipc_has_wan6 wan && fail 'a non-auto wan6 counts'

# x28_mipc reports IPv6 itself without a companion, and only IPv4 plus the link-local with one.
v4_addr=10.0.0.2 prefix=30 v4_gw=10.0.0.1 v4_dns1=1.1.1.1 v4_dns2= ll=fe80::1 v6_global=2001:db8:1:2::5 net64=2001:db8:1:2:: v6_gw= v6_dns1=2001:db8::53 v6_dns2=
defaultroute=1 peerdns=1 metric=0 cid=4 ifname=ccmni1 split6=
: > "$calls"; x28_mipc_send wan
grep -q 'proto_add_ipv6_address 2001:db8:1:2::5 128' "$calls" && grep -q 'proto_add_ipv6_prefix 2001:db8:1:2::/64' "$calls" || fail 'dual-stack wan lost its IPv6'
: > "$calls"; split6=1; x28_mipc_send wan
grep -q 'proto_add_ipv4_address 10.0.0.2 30' "$calls" && grep -q 'proto_add_ipv6_address fe80::1 64' "$calls" || fail 'split wan lost IPv4 or link-local'
grep -q 'proto_add_ipv6_address 2001' "$calls" || grep -q 'proto_add_ipv6_prefix' "$calls" || grep -q 'proto_add_ipv6_route' "$calls" && fail 'split wan still reports the global IPv6'
x28_mipc_publish6 wan
[ "$(cat "$X28_MIPC_RUN/wan.v6")" = "$(printf '2001:db8:1:2::5\n2001:db8:1:2::\n\n2001:db8::53\n')" ] || fail 'state file content'

# Passthrough and split IPv6 coexist: no cellular IPv4 on ccmni, but wan6 still owns the global IPv6.
passthrough_mac=02:00:00:aa:bb:01
: > "$calls"; x28_mipc_send wan
grep -q 'proto_add_ipv4_address' "$calls" && fail 'passthrough installed IPv4 on ccmni'
grep -q 'json_add_string x28_passthrough_ip 10.0.0.2' "$calls" || fail 'passthrough result missing'
grep -q 'proto_add_ipv6_prefix' "$calls" && fail 'passthrough stole wan6 prefix'
x28_mipc_publish6 wan
passthrough_mac=

# x28_mipc6 installs what wan published.
t_defaultroute= t_peerdns= t_metric=
: > "$calls"
proto_x28_mipc6_setup wan6 ccmni1 2>/dev/null || { cat "$calls"; fail 'wan6 setup failed with a published result'; }
printf 'proto_init_update ccmni1 1\nproto_add_ipv6_address 2001:db8:1:2::5 128\nproto_add_ipv6_prefix 2001:db8:1:2::/64\nproto_add_ipv6_route :: 0  0\nproto_add_dns_server 2001:db8::53\nproto_send_update wan6\n' | cmp -s - "$calls" || { cat "$calls"; fail 'wan6 update'; }
: > "$calls"; t_defaultroute=0 t_peerdns=0; proto_x28_mipc6_setup wan6 ccmni1
grep -q 'proto_add_ipv6_route' "$calls" || grep -q 'proto_add_dns_server' "$calls" && fail 'defaultroute/peerdns options ignored'
t_defaultroute= t_peerdns=; : > "$calls"
rm -f "$X28_MIPC_RUN/wan.v6"
proto_x28_mipc6_setup wan6 ccmni1 && fail 'wan6 came up without any IPv6 result'
grep -q 'proto_notify_error wan6 NO_IPV6' "$calls" || fail 'missing result not reported as NO_IPV6'
mkdir -p "$X28_MIPC_RUN"; printf 'garbage\n2001:db8::\n\n\n\n' > "$X28_MIPC_RUN/wan.v6"; : > "$calls"
proto_x28_mipc6_setup wan6 ccmni1 && fail 'a corrupt state file was accepted'
grep -q 'proto_add_ipv6_address' "$calls" && fail 'a corrupt state file installed an address'
proto_x28_mipc6_teardown wan6; grep -q 'proto_init_update \* 0' "$calls" && grep -q 'proto_send_update wan6' "$calls" || fail 'teardown'
# The file appearing while wan6 waits (wan's first update comes before the IPv6 result).
rm -f "$X28_MIPC_RUN/wan.v6"; : > "$calls"; X28_MIPC6_WAIT=5
( sleep 1; x28_mipc_publish6 wan ) &
proto_x28_mipc6_setup wan6 ccmni1 || fail 'wan6 did not wait for the state file'
wait; grep -q 'proto_add_ipv6_address 2001:db8:1:2::5 128' "$calls" || fail 'wan6 update after waiting'
echo 'PASS: wan6 companion: detection, state file, split reporting, install, options and teardown'
