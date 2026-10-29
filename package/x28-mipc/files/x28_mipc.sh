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
 local v4_addr v4_mask v4_gw v4_dns1 v4_dns2 prefix
 json_get_vars apn mtu iptype defaultroute peerdns metric
 mtu="${mtu:-1500}"; iptype="${iptype:-1}"
 defaultroute="${defaultroute:-1}"; peerdns="${peerdns:-1}"; metric="${metric:-0}"
 if [ "$iptype" != 1 ]; then
  proto_notify_error "$interface" IPV4_ONLY
  proto_block_restart "$interface"
  return 1
 fi
 case "$apn" in ''|*[!a-zA-Z0-9._-]*) apn= ;; esac
 if [ -z "$apn" ] || [ "${#apn}" -gt 100 ] ||
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

 # shortcut: IPv4 routing with no PAP/CHAP; extend after modem ABI and IPv6 tests.
 # shortcut: one native WAN interface; multi-bearer ownership needs a modem API audit.
 json_init
 json_add_string apn "$apn"
 json_add_int ip_type 1
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
 json_get_vars result cid ifname v4_addr v4_mask v4_gw v4_dns1 v4_dns2
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
 prefix="$(x28_mipc_prefix "$v4_mask")" || { x28_mipc_fail_owned "$interface" "$cid" INVALID_REPLY; return 1; }
 if [ "$prefix" -eq 0 ] || ! x28_mipc_ipv4 "$v4_addr" || [ "$v4_addr" = 0.0.0.0 ] || [ "$v4_addr" = 255.255.255.255 ] ||
    { [ -n "$v4_gw" ] && ! x28_mipc_ipv4 "$v4_gw"; } ||
    { [ -n "$v4_dns1" ] && ! x28_mipc_ipv4 "$v4_dns1"; } ||
    { [ -n "$v4_dns2" ] && ! x28_mipc_ipv4 "$v4_dns2"; }; then
  x28_mipc_fail_owned "$interface" "$cid" INVALID_REPLY; return 1
 fi
 # The kernel leaves ccmni DOWN after a data call (observed on hardware); $ifname was validated as ccmniN above.
 ip link set dev "$ifname" up >/dev/null 2>&1
 if [ -z "$(ip link show dev "$ifname" up 2>/dev/null)" ]; then
  x28_mipc_fail_owned "$interface" "$cid" LINK_NOT_READY; return 1
 fi
 [ "$v4_gw" != 0.0.0.0 ] || v4_gw=
 proto_init_update "$ifname" 1
 proto_add_ipv4_address "$v4_addr" "$prefix"
 [ "$defaultroute" = 0 ] || proto_add_ipv4_route 0.0.0.0 0 "$v4_gw" "$v4_addr" "$metric"
 if [ "$peerdns" = 1 ]; then
  [ -z "$v4_dns1" ] || [ "$v4_dns1" = 0.0.0.0 ] || proto_add_dns_server "$v4_dns1"
  [ -z "$v4_dns2" ] || [ "$v4_dns2" = 0.0.0.0 ] || [ "$v4_dns2" = "$v4_dns1" ] || proto_add_dns_server "$v4_dns2"
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
