#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Real OpenWrt JSON/proto helpers, with modem and ubus operations replaced.
# OpenWrt's sourced proto helpers use unset optional arguments (not nounset-safe).
stage=$1
case_dir=$2
export TRACE="$case_dir/commands" NOTIFICATIONS="$case_dir/notifications"
export X28_MIPC_LOCKFILE="$case_dir/modem.lock"
export X28_MIPC_APN_CMD="cat $case_dir/sim_apns"
export X28_MIPC_SYSCTL="$case_dir/sysctl"
mkdir -p "$case_dir/sysctl/ccmni7"
: > "$TRACE"
: > "$NOTIFICATIONS"
. /lib/functions.sh
. /lib/netifd/netifd-proto.sh

mipc_wan_cli() {
 printf '%s\n' "$*" >> "$TRACE"
 case "$1" in
  --show_sim_status) cat "$case_dir/sim" ;;
  --data_call_act) cat "$case_dir/reply"; return "$(cat "$case_dir/activate_rc")" ;;
  --data_call_deact) return "$(cat "$case_dir/deactivate_rc")" ;;
  --data_call_get) [ -s "$case_dir/get" ] && cat "$case_dir/get" ;;
  --apn_ia_get) cat "$case_dir/ia" ;;
  --apn_ia_set) [ "$(cat "$case_dir/ia_set_noop")" = 1 ] || printf 'IA apn:%s pdp_type:%s roaming_type:%s bearer_bitmask:0xffffffff\n' "$2" "$3" "$4" > "$case_dir/ia" ;;
  --at_cmd)
   case "$2" in
    at+cereg?) printf 'AT response:\n+CEREG: 0,%s\n\nOK\n' "$(cat "$case_dir/reg")" ;;
    at+c5greg?) printf 'AT response:\n+C5GREG: 0,0\n\nOK\n' ;;
    at+epbse=*) [ "$(cat "$case_dir/epbse_noop")" = 1 ] || echo "${2#at+epbse=}" > "$case_dir/epbse"; printf 'AT response:\nOK\n' ;;
    at+epbse?) printf 'AT response:\n+EPBSE: %s\n\nOK\n' "$(cat "$case_dir/epbse")" ;;
    at+emmchlck=0) echo 0 > "$case_dir/lock"; printf 'AT response:\nOK\n' ;;
    at+emmchlck=1,7,0,*) [ "$(cat "$case_dir/lock_noop")" = 1 ] || echo "${2#at+emmchlck=},0" > "$case_dir/lock"; printf 'AT response:\nOK\n' ;;
    at+emmchlck?) printf 'AT response:\n+EMMCHLCK: %s\n\nOK\n' "$(cat "$case_dir/lock")" ;;
    at+cops=3,2) printf 'AT response:\nOK\n' ;;
    at+cops?) set -- "$1" "$(cat "$case_dir/cops")"; printf 'AT response:\n+COPS: %s,2,"%s",7\n\nOK\n' "${2%% *}" "${2#* }" ;;
    at+cops=0) echo "0 43211" > "$case_dir/cops"; printf 'AT response:\nOK\n' ;;
    at+cops=1,2,*)
     # Like the modem: it can answer an error and still apply (cops_err_applied), or answer OK and not.
     [ "$(cat "$case_dir/cops_set_ok")" = 1 ] || [ "$(cat "$case_dir/cops_err_applied")" = 1 ] || { printf 'AT response:\n+CME ERROR: 3\n'; return 0; }
     [ "$(cat "$case_dir/cops_noop")" = 1 ] || echo "1 $(echo "${2#at+cops=1,2,}" | tr -d '"')" > "$case_dir/cops"
     if [ "$(cat "$case_dir/cops_err_applied")" = 1 ]; then printf 'AT response:\n+CME ERROR: 100\n'; else printf 'AT response:\nOK\n'; fi ;;
    at+cfun=0) printf 'AT response:\nOK\n' ;;
    at+cfun=1) [ "$(cat "$case_dir/cfun_ok")" = 1 ] && printf 'AT response:\nOK\n' ;;
    *) printf 'Unexpected AT command\n' >&2; return 99 ;;
   esac ;;
  *) printf 'Unexpected modem command\n' >&2; return 99 ;;
 esac
}
timeout() {
 shift
 "$@"
 local rc=$?
 [ "$(cat "$case_dir/act_hang")" = 1 ] && return 124
 return $rc
}
ubus() {
 if [ "$1" = call ] && [ "$2" = network.interface ] && [ "$3" = notify_proto ]; then
  printf '%s\n' "$4" >> "$NOTIFICATIONS"
  case "$4" in
   *'"link-up":true'*|*'"link-up": true'*) return "$(cat "$case_dir/notify_rc")" ;;
  esac
  return 0
 fi
 if [ "$1" = call ] && [ "$2" = network.interface.wan ] && [ "$3" = status ]; then
  cat "$case_dir/status"; return "$(cat "$case_dir/status_rc")"
 fi
 printf 'Unexpected ubus call: %s\n' "$*" >&2; return 99
}
ip() {
 if [ "$*" = '-6 addr show dev ccmni7 scope global' ]; then cat "$case_dir/v6_global"; return 0; fi
 case "$*" in '-6 addr del '*' dev ccmni7') printf '%s\n' "$4" >> "$case_dir/ip6del"; return 0 ;; esac
 [ "$*" = 'link show dev ccmni7 up' ] || { printf 'Unexpected ip command\n' >&2; return 99; }
 [ "$(cat "$case_dir/link")" = up ] && printf '7: ccmni7: <UP> mtu 1500\n'
 return 0
}
sleep() { :; }
uci() { printf 'FORBIDDEN uci\n' >> "$TRACE"; return 99; }
killall() { printf 'FORBIDDEN killall\n' >> "$TRACE"; return 99; }
ifup() { printf 'FORBIDDEN ifup\n' >> "$TRACE"; return 99; }
ifdown() { printf 'FORBIDDEN ifdown\n' >> "$TRACE"; return 99; }
pidof() { [ "$1" = wan_mgr ] && [ "$(cat "$case_dir/vendor_active")" = 1 ]; }

export INCLUDE_ONLY=1
. "$stage/package/x28-mipc/files/x28_mipc.sh"
json_load "$(cat "$case_dir/config")"
if [ "$(cat "$case_dir/operation")" = teardown ]; then
 proto_x28_mipc_teardown wan
 rc=$?
elif [ "$(cat "$case_dir/operation")" = locked ]; then
 exec 8>"$X28_MIPC_LOCKFILE"
 flock -n 8 || exit 98
 (proto_x28_mipc_setup wan)
 rc=$?
 flock -u 8
else
 proto_x28_mipc_setup wan
 rc=$?
fi
printf '%s\n' "$rc" > "$case_dir/exit_code"
exit 0
