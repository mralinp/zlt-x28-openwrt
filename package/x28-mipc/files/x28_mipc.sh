#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only

[ -n "$INCLUDE_ONLY" ] || {
 . /lib/functions.sh
 . /lib/netifd/netifd-proto.sh
 init_proto "$@"
}

proto_x28_mipc_init_config() {
 available=1
 no_device=1
 teardown_on_l3_link_down=1
 proto_config_add_string apn
 proto_config_add_int mtu
 proto_config_add_int iptype
 proto_config_add_defaults
}

x28_mipc_uint() {
 case "$1" in ''|*[!0-9]*) return 1 ;; esac
 [ "${#1}" -le 10 ] && [ "$1" -le "$2" ]
}

x28_mipc_ipv4() {
 case "$1" in ''|.*|*.|*..*|*[!0-9.]*) return 1 ;; esac
 local IFS=. octet
 set -- $1
 [ "$#" -eq 4 ] || return 1
 for octet in "$@"; do
  case "$octet" in 0|[1-9]|[1-9][0-9]|[1-9][0-9][0-9]) ;; *) return 1 ;; esac
  [ "$octet" -le 255 ] || return 1
 done
}

x28_mipc_prefix() {
 case "$1" in
  *.*) ;;
  *) x28_mipc_uint "$1" 32 || return 1; printf '%s\n' "$1"; return 0 ;;
 esac
 x28_mipc_ipv4 "$1" || return 1
 local IFS=. octet bits prefix=0 ended=0
 set -- $1
 for octet in "$@"; do
  [ "$ended" -eq 0 ] || [ "$octet" -eq 0 ] || return 1
  case "$octet" in
   255) bits=8 ;; 254) bits=7 ;; 252) bits=6 ;; 248) bits=5 ;;
   240) bits=4 ;; 224) bits=3 ;; 192) bits=2 ;; 128) bits=1 ;; 0) bits=0 ;;
   *) return 1 ;;
  esac
  prefix=$((prefix + bits))
  [ "$octet" -eq 255 ] || ended=1
 done
 printf '%s\n' "$prefix"
}

x28_mipc_ipv6() {
 case "$1" in *:*) ;; *) return 1 ;; esac
 case "$1" in *[!0-9a-fA-F:]*|*:::*|*::*::*) return 1 ;; esac
 [ "${#1}" -le 39 ]
}

# The first 64 bits of a valid IPv6 address as "g1:g2:g3:g4::".
x28_mipc_net64() {
 local a="$1" count=0 fill= g IFS=:
 for g in $a; do [ -z "$g" ] || count=$((count + 1)); done
 case "$a" in
  *::*)
   while [ "$count" -lt 8 ]; do fill="${fill}0:"; count=$((count + 1)); done
   a="${a%%::*}:$fill${a#*::}" ;;
 esac
 a="${a#:}"; a="${a%:}"
 set -- $a
 [ "$#" -eq 8 ] || return 1
 printf '%s:%s:%s:%s::\n' "$1" "$2" "$3" "$4"
}

x28_mipc_run_locked() {
 local interface="$1" operation="$2" rc
 shift 2
 # Tests redirect this lock to their private /tmp staging directory.
 local lockfile="${X28_MIPC_LOCKFILE:-/var/lock/x28-mipc.lock}"
 exec 9>"$lockfile"
 if ! flock -n 9; then
  proto_notify_error "$interface" MODEM_BUSY
  exec 9>&-
  return 1
 fi
 "$operation" "$interface" "$@"
 rc=$?
 flock -u 9
 exec 9>&-
 return "$rc"
}

x28_mipc_fail_owned() {
 local interface="$1" cid="$2" error="$3"
 if ! mipc_wan_cli --data_call_deact "$cid" >/dev/null 2>&1; then
  proto_notify_error "$interface" CLEANUP_FAILED
  proto_block_restart "$interface"
  return 1
 fi
 proto_init_update "*" 0
 proto_send_update "$interface" >/dev/null 2>&1
 proto_notify_error "$interface" "$error"
 return 1
}

x28_mipc_setup() {
 local interface="$1" apn mtu iptype defaultroute peerdns metric sim reply result cid ifname
 local v4_addr v4_mask v4_gw v4_dns1 v4_dns2 prefix v6_addr v6_prefix v6_gw v6_dns1 v6_dns2 net64
 json_get_vars apn mtu iptype defaultroute peerdns metric
 mtu="${mtu:-1500}"; iptype="${iptype:-3}"
 defaultroute="${defaultroute:-1}"; peerdns="${peerdns:-1}"; metric="${metric:-0}"
 # Empty APN = automatic from the SIM, resolved once the SIM is ready.
 if { [ -n "$apn" ] && { [ "${#apn}" -gt 100 ] || case "$apn" in *[!a-zA-Z0-9._-]*) true ;; *) false ;; esac; }; } ||
    { [ "$iptype" != 1 ] && [ "$iptype" != 2 ] && [ "$iptype" != 3 ]; } ||
    ! x28_mipc_uint "$mtu" 1500 || [ "$mtu" -lt 576 ] ||
    ! x28_mipc_uint "$metric" 65535 ||
    { [ "$defaultroute" != 0 ] && [ "$defaultroute" != 1 ]; } ||
    { [ "$peerdns" != 0 ] && [ "$peerdns" != 1 ]; }; then
  proto_notify_error "$interface" INVALID_CONFIG
  proto_block_restart "$interface"
  return 1
 fi
 if pidof wan_mgr >/dev/null 2>&1; then
  proto_notify_error "$interface" VENDOR_WAN_ACTIVE
  proto_block_restart "$interface"
  return 1
 fi
 command -v mipc_wan_cli >/dev/null 2>&1 || { proto_notify_error "$interface" MISSING_MODEM_CLI; return 1; }
 sim="$(mipc_wan_cli --show_sim_status 2>/dev/null)" || { proto_notify_error "$interface" SIM_NOT_READY; return 1; }
 case "$sim" in
  MIPC_SIM_STATUS_COMPLETE_READY) ;;
  MIPC_SIM_STATUS_SIM_PIN|MIPC_SIM_STATUS_SIM_PUK)
   proto_notify_error "$interface" SIM_PIN_LOCKED
   proto_block_restart "$interface"; return 1 ;;
  *) proto_notify_error "$interface" SIM_NOT_READY; return 1 ;;
 esac
 if [ -z "$apn" ]; then
  # Tests replace the lookup through X28_MIPC_APN_CMD.
  apn="$(${X28_MIPC_APN_CMD:-x28-apn} 2>/dev/null | head -n 1 | cut -f 2)"
  case "$apn" in ''|*[!a-zA-Z0-9._-]*) proto_notify_error "$interface" NO_SIM_APN; return 1 ;; esac
 fi

 # shortcut: no PAP/CHAP; add auth when an operator needs it.
 # shortcut: one native WAN interface; multi-bearer ownership needs a modem API audit.
 json_init
 json_add_string apn "$apn"
 json_add_int ip_type "$iptype"
 json_add_int roaming_type 3
 json_add_int auth_type 0
 json_add_string username ""
 json_add_string password ""
 json_add_string bearer_bitmask "0xfffdffff"
 json_add_int mtu "$mtu"
 json_add_int mode 1
 reply="$(mipc_wan_cli --data_call_act "$(json_dump)" 2>/dev/null)" || {
  proto_notify_error "$interface" CONNECT_FAILED; return 1;
 }
 if ! json_load "$reply"; then
  proto_notify_error "$interface" INVALID_REPLY
  proto_block_restart "$interface"; return 1
 fi
 json_get_vars result cid ifname v4_addr v4_mask v4_gw v4_dns1 v4_dns2 v6_addr v6_prefix v6_gw v6_dns1 v6_dns2
 if ! x28_mipc_uint "$result" 2147483647; then
  proto_notify_error "$interface" INVALID_REPLY
  proto_block_restart "$interface"; return 1
 fi
 [ "$result" = 0 ] || { proto_notify_error "$interface" CONNECT_FAILED; return 1; }
 if ! x28_mipc_uint "$cid" 2147483647; then
  proto_notify_error "$interface" INVALID_REPLY
  proto_block_restart "$interface"; return 1
 fi
 case "$ifname" in ccmni[0-9]|ccmni[0-9][0-9]) ;; *) x28_mipc_fail_owned "$interface" "$cid" INVALID_REPLY; return 1 ;; esac
 # IPv4v6 may come back with one family only; IPv4 or IPv6 alone needs that family.
 [ "$iptype" = 2 ] && v4_addr=
 [ "$iptype" = 1 ] && v6_addr=
 if [ -z "$v4_addr$v6_addr" ] || { [ "$iptype" = 1 ] && [ -z "$v4_addr" ]; } || { [ "$iptype" = 2 ] && [ -z "$v6_addr" ]; }; then
  x28_mipc_fail_owned "$interface" "$cid" INVALID_REPLY; return 1
 fi
 if [ -n "$v4_addr" ]; then
  prefix="$(x28_mipc_prefix "$v4_mask")" || { x28_mipc_fail_owned "$interface" "$cid" INVALID_REPLY; return 1; }
  if [ "$prefix" -eq 0 ] || ! x28_mipc_ipv4 "$v4_addr" || [ "$v4_addr" = 0.0.0.0 ] || [ "$v4_addr" = 255.255.255.255 ] ||
     { [ -n "$v4_gw" ] && ! x28_mipc_ipv4 "$v4_gw"; } ||
     { [ -n "$v4_dns1" ] && ! x28_mipc_ipv4 "$v4_dns1"; } ||
     { [ -n "$v4_dns2" ] && ! x28_mipc_ipv4 "$v4_dns2"; }; then
   x28_mipc_fail_owned "$interface" "$cid" INVALID_REPLY; return 1
  fi
 fi
 if [ -n "$v6_addr" ]; then
  v6_prefix="${v6_prefix:-64}"
  if ! x28_mipc_ipv6 "$v6_addr" || ! x28_mipc_uint "$v6_prefix" 128 ||
     { [ -n "$v6_gw" ] && ! x28_mipc_ipv6 "$v6_gw"; } ||
     { [ -n "$v6_dns1" ] && ! x28_mipc_ipv6 "$v6_dns1"; } ||
     { [ -n "$v6_dns2" ] && ! x28_mipc_ipv6 "$v6_dns2"; }; then
   x28_mipc_fail_owned "$interface" "$cid" INVALID_REPLY; return 1
  fi
  # 3GPP hands the UE a whole /64; it goes to netifd as a prefix for the LAN (stock does the same).
  [ "$v6_prefix" = 64 ] && net64="$(x28_mipc_net64 "$v6_addr")"
 fi
 # The kernel leaves ccmni DOWN after a data call (observed on hardware); $ifname was validated as ccmniN above.
 ip link set dev "$ifname" up >/dev/null 2>&1
 if [ -z "$(ip link show dev "$ifname" up 2>/dev/null)" ]; then
  x28_mipc_fail_owned "$interface" "$cid" LINK_NOT_READY; return 1
 fi
 [ "$v4_gw" != 0.0.0.0 ] || v4_gw=
 [ "$v6_gw" != :: ] || v6_gw=
 proto_init_update "$ifname" 1
 if [ -n "$v4_addr" ]; then
  proto_add_ipv4_address "$v4_addr" "$prefix"
  [ "$defaultroute" = 0 ] || proto_add_ipv4_route 0.0.0.0 0 "$v4_gw" "$v4_addr" "$metric"
  if [ "$peerdns" = 1 ]; then
   [ -z "$v4_dns1" ] || [ "$v4_dns1" = 0.0.0.0 ] || proto_add_dns_server "$v4_dns1"
   [ -z "$v4_dns2" ] || [ "$v4_dns2" = 0.0.0.0 ] || [ "$v4_dns2" = "$v4_dns1" ] || proto_add_dns_server "$v4_dns2"
  fi
 fi
 if [ -n "$v6_addr" ]; then
  proto_add_ipv6_address "$v6_addr" 128
  [ -z "$net64" ] || proto_add_ipv6_prefix "${net64}/64"
  [ "$defaultroute" = 0 ] || proto_add_ipv6_route :: 0 "$v6_gw" "$metric"
  if [ "$peerdns" = 1 ]; then
   [ -z "$v6_dns1" ] || proto_add_dns_server "$v6_dns1"
   [ -z "$v6_dns2" ] || [ "$v6_dns2" = "$v6_dns1" ] || proto_add_dns_server "$v6_dns2"
  fi
 fi
 proto_add_data
 json_add_int x28_mipc_cid "$cid"
 json_add_string x28_mipc_owner "$interface"
 proto_close_data
 proto_send_update "$interface" || { x28_mipc_fail_owned "$interface" "$cid" NOTIFY_FAILED; return 1; }
}

x28_mipc_teardown() {
 local interface="$1" snapshot x28_mipc_cid x28_mipc_owner
 snapshot="$(ubus call "network.interface.$interface" status)" || { proto_notify_error "$interface" STATUS_UNAVAILABLE; return 1; }
 json_load "$snapshot" || { proto_notify_error "$interface" STATUS_UNAVAILABLE; return 1; }
 if json_select data; then
  json_get_vars x28_mipc_cid x28_mipc_owner
 fi
 if [ -n "$x28_mipc_owner$x28_mipc_cid" ]; then
  if [ "$x28_mipc_owner" != "$interface" ] || ! x28_mipc_uint "$x28_mipc_cid" 2147483647; then
   proto_notify_error "$interface" OWNERSHIP_MISMATCH; return 1
  fi
  if ! mipc_wan_cli --data_call_deact "$x28_mipc_cid" >/dev/null 2>&1; then
   proto_notify_error "$interface" DEACTIVATE_FAILED
   proto_block_restart "$interface"; return 1
  fi
 fi
 proto_init_update "*" 0
 proto_send_update "$interface"
}

proto_x28_mipc_setup() { x28_mipc_run_locked "$1" x28_mipc_setup; }
proto_x28_mipc_teardown() { x28_mipc_run_locked "$1" x28_mipc_teardown; }

[ -n "$INCLUDE_ONLY" ] || add_protocol x28_mipc
