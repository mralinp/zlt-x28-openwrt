#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# `wan6` for the X28's cellular WAN: proto x28_mipc6 on device '@wan' (#648). The x28_mipc interface owns the data call and
# publishes the bearer's IPv6 result in /var/run/x28_mipc/<wan>.v6 (address, /64 network, gateway, DNS 1, DNS 2, one per line);
# this interface installs it as its own address, default route, LAN prefix and DNS, so wan and wan6 are two ordinary interfaces
# (LuCI, the firewall zone and mwan3 see both). It goes down with wan; with no IPv6 on the bearer it stays down.

[ -n "$INCLUDE_ONLY" ] || {
 . /lib/functions.sh
 . /lib/netifd/netifd-proto.sh
 init_proto "$@"
}

proto_x28_mipc6_init_config() {
 proto_config_add_defaults
}

proto_x28_mipc6_setup() {
 local interface="$1" device="$2" parent f i defaultroute peerdns metric g net64 gw d1 d2
 json_get_vars defaultroute peerdns metric
 defaultroute="${defaultroute:-1}"; peerdns="${peerdns:-1}"; metric="${metric:-0}"
 parent="$(uci -q get "network.$interface.device")"; parent="${parent#@}"
 [ -n "$parent" ] || { proto_notify_error "$interface" NO_PARENT; proto_block_restart "$interface"; return 1; }
 f="${X28_MIPC_RUN:-/var/run/x28_mipc}/$parent.v6"
 # wan reports its link-local first and the global address after the RA wait (up to 10 s), so this can start before the file exists.
 i=0
 while [ ! -r "$f" ] && [ "$i" -lt "${X28_MIPC6_WAIT:-30}" ]; do sleep 1; i=$((i + 1)); done
 [ -r "$f" ] && {
  IFS= read -r g && IFS= read -r net64 && IFS= read -r gw && IFS= read -r d1 && IFS= read -r d2
 } < "$f" && [ -n "$g" ] && [ -n "$net64" ] ||
  { proto_notify_error "$interface" NO_IPV6; proto_block_restart "$interface"; return 1; }
 proto_init_update "$device" 1
 proto_add_ipv6_address "$g" 128
 proto_add_ipv6_prefix "${net64}/64"
 [ "$defaultroute" = 0 ] || proto_add_ipv6_route :: 0 "$gw" "$metric"
 if [ "$peerdns" = 1 ]; then
  [ -z "$d1" ] || proto_add_dns_server "$d1"
  [ -z "$d2" ] || [ "$d2" = "$d1" ] || proto_add_dns_server "$d2"
 fi
 proto_send_update "$interface"
}

proto_x28_mipc6_teardown() {
 proto_init_update "*" 0
 proto_send_update "$1"
}

[ -n "$INCLUDE_ONLY" ] || add_protocol x28_mipc6
