#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Real OpenWrt JSON/proto helpers, with modem and ubus operations replaced.
# OpenWrt's sourced proto helpers use unset optional arguments (not nounset-safe).
stage=$1
case_dir=$2
export TRACE="$case_dir/commands" NOTIFICATIONS="$case_dir/notifications"
export X28_MIPC_LOCKFILE="$case_dir/modem.lock"
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
  *) printf 'Unexpected modem command\n' >&2; return 99 ;;
 esac
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
 [ "$*" = 'link show dev ccmni7 up' ] || { printf 'Unexpected ip command\n' >&2; return 99; }
 [ "$(cat "$case_dir/link")" = up ] && printf '7: ccmni7: <UP> mtu 1500\n'
 return 0
}
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
