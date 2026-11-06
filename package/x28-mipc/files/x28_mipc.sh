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
 proto_config_add_boolean roaming
 proto_config_add_string plmn
 proto_config_add_string celllock
 proto_config_add_string lteband_mode
 proto_config_add_array 'lteband_list:uinteger'
 proto_config_add_defaults
}

x28_mipc_uint() {
 case "$1" in ''|*[!0-9]*) return 1 ;; esac
 [ "${#1}" -le 10 ] && [ "$1" -le "$2" ]
}

# Registration state from the modem's AT view: 1 home, 5 roaming. CEREG covers LTE/NSA, C5GREG covers SA.
x28_mipc_reg() {
 local cmd stat
 for cmd in cereg c5greg; do
  stat="$(mipc_wan_cli --at_cmd "at+$cmd?" 2>/dev/null | sed -n 's/^+C[0-9A-Z]*REG: *[0-9]*,\([0-9]*\).*/\1/p' | head -n 1)"
  case "$stat" in 1|5) echo "$stat"; return 0 ;; esac
 done
 return 1
}

# mipc_wan_cli exits 0 whatever happened (SDK main), so AT results are judged by their OK line.
x28_mipc_cfun_on() {
 local i
 for i in 1 2 3; do
  mipc_wan_cli --at_cmd at+cfun=1 2>/dev/null | grep -q '^OK' && return 0
  sleep 1
 done
 return 1
}

x28_mipc_wait_reg() {
 local i=0
 until x28_mipc_reg >/dev/null; do
  [ "$i" -ge 40 ] && return 1
  sleep 1; i=$((i + 1))
 done
}

# 0 when the modem's attach profile is exactly $1 (APN, case-insensitive) $2 (PDP type) with roaming type 3.
x28_mipc_ia_match() {
 local ia
 ia="$(mipc_wan_cli --apn_ia_get 2>/dev/null | sed -n 's/^IA apn:\([^ ]*\) pdp_type:\([0-9]*\) roaming_type:\([0-9]*\).*/\1 \2 \3/p' | head -n 1)"
 [ "$(echo "${ia%% *}" | tr 'A-Z' 'a-z')" = "$(echo "$1" | tr 'A-Z' 'a-z')" ] && [ "${ia#* }" = "$2 3" ]
}

# The vendor dialer rewrites the initial-attach APN (ql_ia_apn_set) instead of asking for a second PDN, and a PDN
# whose APN differs from the attach one is refused (observed, result 1314103, on a roaming SIM). Same as the SDK's check_ia.
x28_mipc_sync_attach() {
 if x28_mipc_ia_match "$1" "$2"; then
  # In sync but not registered: an earlier attempt may have left the radio off.
  x28_mipc_reg >/dev/null && return 0
  x28_mipc_cfun_on && x28_mipc_wait_reg
  return
 fi
 mipc_wan_cli --apn_ia_set "$1" "$2" 3 >/dev/null 2>&1
 x28_mipc_ia_match "$1" "$2" || return 1
 # The attach profile applies on the next attach.
 mipc_wan_cli --at_cmd at+cfun=0 >/dev/null 2>&1
 sleep 2
 x28_mipc_cfun_on && x28_mipc_wait_reg
}

# "<mode> <oper>" from +COPS: <mode>,<format>,"<oper>",<act>; mode 0 automatic, 1 manual.
x28_mipc_cops() {
 mipc_wan_cli --at_cmd 'at+cops?' 2>/dev/null | sed -n 's/^+COPS: *\([0-9]*\)\(,[0-9]*,"\([0-9]*\)"\)\{0,1\}.*/\1 \3/p' | head -n 1
}

# Operator: empty = automatic, else manual selection of that numeric PLMN (like the vendor's network search).
# The modem answers +CME ERROR 100 to AT+COPS=1 yet applies it (observed), so the result is read back, not taken from
# the reply. A manual choice that does not register is set back to automatic.
x28_mipc_operator() {
 local want="$1" want_mode=0 i=0
 mipc_wan_cli --at_cmd 'at+cops=3,2' >/dev/null 2>&1
 [ -z "$want" ] || want_mode=1
 [ "$(x28_mipc_cops)" = "$want_mode${want:+ $want}" ] && return 0
 [ -n "$want" ] || [ "$(x28_mipc_cops | cut -d' ' -f1)" != 0 ] || return 0
 if [ -n "$want" ]; then
  mipc_wan_cli --at_cmd "at+cops=1,2,\"$want\"" >/dev/null 2>&1
 else
  mipc_wan_cli --at_cmd 'at+cops=0' >/dev/null 2>&1
 fi
 until [ "$(x28_mipc_cops | cut -d' ' -f1)" = "$want_mode" ] && { [ -z "$want" ] || [ "$(x28_mipc_cops | cut -d' ' -f2)" = "$want" ]; } && x28_mipc_reg >/dev/null; do
  [ "$i" -ge 60 ] && break
  sleep 1; i=$((i + 1))
 done
 [ "$i" -lt 60 ] && return 0
 mipc_wan_cli --at_cmd 'at+cops=0' >/dev/null 2>&1
 return 1
}

# LTE band lock via AT+EPBSE=<gsm>,<umts>,<lte 1-32>,<lte 33-64>,<4 more> (the last four read 0 here; GSM, UMTS and those are
# kept as read). Supported LTE bands of this modem (RG500L-EU): 1 3 5 7 8 20 28 32 and 38 40 41 42 43.
# lteband_mode: none | allow (only the listed bands) | deny (all but the listed). A change re-registers the modem, so it
# is applied before the data call; a mask that does not read back or has no service is put back as it was.
X28_MIPC_LTE_LO=2282225877
X28_MIPC_LTE_HI=1952

x28_mipc_epbse() {
 mipc_wan_cli --at_cmd "$1" 2>/dev/null | sed -n 's/^+EPBSE: *\([0-9,]*\).*/\1/p' | head -n 1
}

x28_mipc_bandlock() {
 local mode="$1" list="$2" cur lo hi b lo_l=0 hi_l=0 want i=0 old
 cur="$(x28_mipc_epbse 'at+epbse?')"
 case "$cur" in [0-9]*,[0-9]*,[0-9]*,[0-9]*,[0-9]*,[0-9]*,[0-9]*,[0-9]*,[0-9]*,[0-9]*) ;; *) return 1 ;; esac
 for b in $list; do
  if [ "$b" -le 32 ]; then lo_l=$((lo_l | (1 << (b - 1)))); else hi_l=$((hi_l | (1 << (b - 33)))); fi
 done
 case "$mode" in
  allow) lo=$((lo_l & X28_MIPC_LTE_LO)); hi=$((hi_l & X28_MIPC_LTE_HI)) ;;
  deny) lo=$((X28_MIPC_LTE_LO & ~lo_l)); hi=$((X28_MIPC_LTE_HI & ~hi_l)) ;;
  *) lo=$X28_MIPC_LTE_LO; hi=$X28_MIPC_LTE_HI ;;
 esac
 [ $((lo | hi)) -ne 0 ] || return 1
 old="$cur"
 want="$(echo "$cur" | cut -d, -f1,2),$lo,$hi,$(echo "$cur" | cut -d, -f5-)"
 [ "$cur" = "$want" ] && return 0
 mipc_wan_cli --at_cmd "at+epbse=$want" >/dev/null 2>&1
 until [ "$(x28_mipc_epbse 'at+epbse?')" = "$want" ]; do
  [ "$i" -ge 10 ] && break
  sleep 1; i=$((i + 1))
 done
 if [ "$i" -lt 10 ]; then
  sleep 3
  x28_mipc_wait_reg && return 0
 fi
 mipc_wan_cli --at_cmd "at+epbse=$old" >/dev/null 2>&1
 return 1
}

# Every listed band must be one of the modem's supported LTE bands.
x28_mipc_bands_ok() {
 local b
 for b in $1; do
  case " 1 3 5 7 8 20 28 32 38 40 41 42 43 " in *" $b "*) ;; *) return 1 ;; esac
 done
}

# "<earfcn>:<pci>", no leading zeros, EARFCN up to 46589 and PCI up to 511.
x28_mipc_cell_ok() {
 case "$1" in ''|:*|*:|*:*:*|*[!0-9:]*|0[0-9]*|*:0[0-9]*) return 1 ;; *:*) ;; *) return 1 ;; esac
 x28_mipc_uint "${1%:*}" 46589 && x28_mipc_uint "${1#*:}" 511
}

# LTE cell lock "<earfcn>:<pci>" (AT+EMMCHLCK; its range excludes NR on this modem), empty = off. Locking re-selects the
# cell and drops the bearer, so it is applied before the data call. Only a positive read counts: "off" for
# +EMMCHLCK: 0, the cell for a lock, empty when unreadable (the CLI sometimes crashes). A lock that does not hold or has
# no service is undone, also when it was already set by an earlier, interrupted attempt.
x28_mipc_celllock() {
 local want="$1" i=0
 x28_mipc_lockread() {
  mipc_wan_cli --at_cmd 'at+emmchlck?' 2>/dev/null | sed -n 's/^+EMMCHLCK: *0.*/off/p; s/^+EMMCHLCK: *1,7,0,\([0-9]*\),\([0-9]*\).*/\1:\2/p' | head -n 1
 }
 if [ -z "$want" ]; then
  [ "$(x28_mipc_lockread)" = off ] && return 0
  mipc_wan_cli --at_cmd 'at+emmchlck=0' >/dev/null 2>&1
  until [ "$(x28_mipc_lockread)" = off ]; do
   [ "$i" -ge 10 ] && return 1
   sleep 1; i=$((i + 1))
  done
  return 0
 fi
 if [ "$(x28_mipc_lockread)" != "$want" ]; then
  mipc_wan_cli --at_cmd "at+emmchlck=1,7,0,${want%:*},${want#*:}" >/dev/null 2>&1
  until [ "$(x28_mipc_lockread)" = "$want" ]; do
   [ "$i" -ge 10 ] && break
   sleep 1; i=$((i + 1))
  done
  sleep 3
 fi
 [ "$i" -lt 10 ] && x28_mipc_wait_reg && return 0
 mipc_wan_cli --at_cmd 'at+emmchlck=0' >/dev/null 2>&1
 return 1
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

x28_mipc_v6_valid() {
 x28_mipc_ipv6 "$v6_addr" &&
 { [ -z "$v6_gw" ] || x28_mipc_ipv6 "$v6_gw"; } &&
 { [ -z "$v6_dns1" ] || x28_mipc_ipv6 "$v6_dns1"; } &&
 { [ -z "$v6_dns2" ] || x28_mipc_ipv6 "$v6_dns2"; }
}

# Fills the caller's v6_* from data_call_get when it describes this ccmni.
x28_mipc_v6_from_get() {
 local reply iface
 reply="$(mipc_wan_cli --data_call_get 2>/dev/null)" && json_load "$reply" 2>/dev/null || return 1
 json_get_vars iface
 [ "$iface" = "$1" ] || return 1
 json_get_vars v6_addr v6_gw v6_dns1 v6_dns2
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
 local interface="$1" apn mtu iptype roaming plmn celllock lteband_mode defaultroute peerdns metric sim rc reply result cid ifname
 local v4_addr v4_mask v4_gw v4_dns1 v4_dns2 prefix v6_addr v6_gw v6_dns1 v6_dns2 v6_global net64 i ll
 json_get_vars apn mtu iptype roaming plmn celllock lteband_mode defaultroute peerdns metric
 local bands="" b
 json_get_values bands lteband_list
 mtu="${mtu:-1500}"; iptype="${iptype:-3}"; roaming="${roaming:-0}"
 defaultroute="${defaultroute:-1}"; peerdns="${peerdns:-1}"; metric="${metric:-0}"
 # Empty APN = automatic from the SIM, resolved once the SIM is ready.
 if { [ -n "$apn" ] && { [ "${#apn}" -gt 100 ] || case "$apn" in -*|*[!a-zA-Z0-9._-]*) true ;; *) false ;; esac; }; } ||
    { [ "$iptype" != 1 ] && [ "$iptype" != 2 ] && [ "$iptype" != 3 ]; } ||
    ! x28_mipc_uint "$mtu" 1500 || [ "$mtu" -lt 576 ] ||
    ! x28_mipc_uint "$metric" 65535 ||
    { [ -n "$celllock" ] && ! x28_mipc_cell_ok "$celllock"; } ||
    { [ -n "$lteband_mode" ] && [ "$lteband_mode" != none ] && [ "$lteband_mode" != allow ] && [ "$lteband_mode" != deny ]; } ||
    ! x28_mipc_bands_ok "$bands" ||
    { [ "$roaming" != 0 ] && [ "$roaming" != 1 ]; } ||
    { [ -n "$plmn" ] && { [ "${#plmn}" -lt 5 ] || [ "${#plmn}" -gt 6 ] || case "$plmn" in *[!0-9]*) true ;; *) false ;; esac; }; } ||
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
  case "$apn" in ''|-*|*[!a-zA-Z0-9._-]*) proto_notify_error "$interface" NO_SIM_APN; return 1 ;; esac
 fi

 x28_mipc_operator "$plmn" || { proto_notify_error "$interface" OPERATOR_FAILED; return 1; }
 x28_mipc_celllock "$celllock" || { proto_notify_error "$interface" CELL_LOCK_FAILED; proto_block_restart "$interface"; return 1; }
 [ -z "$lteband_mode" ] || x28_mipc_bandlock "$lteband_mode" "$bands" || { proto_notify_error "$interface" BAND_LOCK_FAILED; proto_block_restart "$interface"; return 1; }
 # Roaming is off by default, like the vendor's data-roaming switch: refuse the bearer while roaming unless asked.
 if [ "$roaming" != 1 ] && [ "$(x28_mipc_reg)" = 5 ]; then
  proto_notify_error "$interface" ROAMING_DISABLED; return 1
 fi
 x28_mipc_sync_attach "$apn" "$iptype" || { proto_notify_error "$interface" ATTACH_FAILED; return 1; }

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
 reply="$(timeout 30 mipc_wan_cli --data_call_act "$(json_dump)" 2>/dev/null)"
 rc=$?
 if [ "$rc" = 124 ]; then
  # After a teardown the modem may never answer (observed, #337); a radio cycle clears it, then netifd retries.
  mipc_wan_cli --at_cmd at+cfun=0 >/dev/null 2>&1
  sleep 2
  x28_mipc_cfun_on && x28_mipc_wait_reg
  proto_notify_error "$interface" CONNECT_TIMEOUT; return 1
 fi
 [ "$rc" = 0 ] || { proto_notify_error "$interface" CONNECT_FAILED; return 1; }
 if ! json_load "$reply"; then
  proto_notify_error "$interface" INVALID_REPLY
  proto_block_restart "$interface"; return 1
 fi
 json_get_vars result cid ifname v4_addr v4_mask v4_gw v4_dns1 v4_dns2 v6_addr v6_gw v6_dns1 v6_dns2
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
 # IPv4v6 may come back with one family only; IPv4 alone needs it now, IPv6 is checked once the RA had its chance.
 [ "$iptype" = 2 ] && v4_addr=
 [ "$iptype" = 1 ] && v6_addr=
 if [ "$iptype" = 1 ] && [ -z "$v4_addr" ]; then
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
 if [ -n "$v6_addr" ] && ! x28_mipc_v6_valid; then
  x28_mipc_fail_owned "$interface" "$cid" INVALID_REPLY; return 1
 fi
 # The kernel leaves ccmni DOWN after a data call (observed on hardware); $ifname was validated as ccmniN above.
 ip link set dev "$ifname" up >/dev/null 2>&1
 if [ -z "$(ip link show dev "$ifname" up 2>/dev/null)" ]; then
  x28_mipc_fail_owned "$interface" "$cid" LINK_NOT_READY; return 1
 fi
 [ "$v4_gw" != 0.0.0.0 ] || v4_gw=
 if [ "$iptype" != 1 ]; then
  # The modem reports only the interface ID (fe80::...); the global /64 arrives by RA on ccmni and the kernel
  # configures it (stock's check_global_ipv6_addr waits the same way). 3GPP routes that whole /64 to the UE.
  # ccmni has no MAC: the kernel needs this link-local to solicit the RA and takes its IID for SLAAC. It goes to
  # netifd in a first update; netifd flushes addresses it does not own when it takes the device (observed).
  # Tests redirect this to their private staging directory.
  local pinfo="${X28_MIPC_SYSCTL:-/proc/sys/net/ipv6/conf}/$ifname/accept_ra_pinfo"
  # The sysctl init zeroes accept_ra everywhere, and with forwarding on the kernel solicits only at 2 (observed: no RS).
  echo 2 > "${pinfo%_pinfo}" 2>/dev/null
  echo 1 > "$pinfo" 2>/dev/null
  i=0 ll=
  while :; do
   # Reusing the already-active attach bearer, the activation reply omits IPv6 (observed); data_call_get has it.
   if [ -z "$v6_addr" ] && x28_mipc_v6_from_get "$ifname" && [ -n "$v6_addr" ] && ! x28_mipc_v6_valid; then
    x28_mipc_fail_owned "$interface" "$cid" INVALID_REPLY; return 1
   fi
   [ "$v6_gw" != :: ] || v6_gw=
   if [ -z "$ll" ]; then
    case "$v6_addr" in
     [fF][eE]8*) ll="$v6_addr"; x28_mipc_send "$interface" || { x28_mipc_fail_owned "$interface" "$cid" NOTIFY_FAILED; return 1; } ;;
    esac
   fi
   v6_global="$(ip -6 addr show dev "$ifname" scope global 2>/dev/null | sed -n 's/.*inet6 \([0-9a-fA-F:]*\)\/64 .*/\1/p' | head -n 1)"
   [ -n "$v6_global" ] || [ "$i" -ge 10 ] && break
   sleep 1; i=$((i + 1))
  done
  case "$v6_addr" in [fF][eE]8*) ;; *) v6_global="${v6_global:-$v6_addr}" ;; esac
  if x28_mipc_ipv6 "$v6_global"; then
   net64="$(x28_mipc_net64 "$v6_global")"
   # The /64 belongs to the LAN now: keep the WAN to a /128 so the kernel's on-link /64 route on ccmni does not
   # beat the LAN's (observed: replies to LAN clients left through ccmni). Bearer prefixes do not change.
   echo 0 > "$pinfo" 2>/dev/null
   ip -6 addr del "$v6_global/64" dev "$ifname" >/dev/null 2>&1
  else
   v6_global=
   [ -n "$v4_addr" ] || { x28_mipc_fail_owned "$interface" "$cid" NO_IPV6; return 1; }
  fi
 fi
 x28_mipc_send "$interface" || { x28_mipc_fail_owned "$interface" "$cid" NOTIFY_FAILED; return 1; }
}

# Sends the caller's (x28_mipc_setup) current addresses, routes and DNS to netifd.
x28_mipc_send() {
 proto_init_update "$ifname" 1
 if [ -n "$v4_addr" ]; then
  proto_add_ipv4_address "$v4_addr" "$prefix"
  [ "$defaultroute" = 0 ] || proto_add_ipv4_route 0.0.0.0 0 "$v4_gw" "$v4_addr" "$metric"
  if [ "$peerdns" = 1 ]; then
   [ -z "$v4_dns1" ] || [ "$v4_dns1" = 0.0.0.0 ] || proto_add_dns_server "$v4_dns1"
   [ -z "$v4_dns2" ] || [ "$v4_dns2" = 0.0.0.0 ] || [ "$v4_dns2" = "$v4_dns1" ] || proto_add_dns_server "$v4_dns2"
  fi
 fi
 [ -z "$ll" ] || proto_add_ipv6_address "$ll" 64
 if [ -n "$v6_global" ]; then
  proto_add_ipv6_address "$v6_global" 128
  proto_add_ipv6_prefix "${net64}/64"
  [ "$defaultroute" = 0 ] || proto_add_ipv6_route :: 0 "$v6_gw" "$metric"
  if [ "$peerdns" = 1 ]; then
   [ -z "$v6_dns1" ] || proto_add_dns_server "$v6_dns1"
   [ -z "$v6_dns2" ] || [ "$v6_dns2" = "$v6_dns1" ] || proto_add_dns_server "$v6_dns2"
  fi
 fi
 proto_add_data
 json_add_int x28_mipc_cid "$cid"
 json_add_string x28_mipc_owner "$1"
 proto_close_data
 proto_send_update "$1"
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
