#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# netifd wireless handler for the X28's MT7915 DBDC on MediaTek's mt_wifi driver (no nl80211). The driver reads
# /etc/wireless/l1profile.dat and one .dat profile per band (merged into DBDC_card0.dat) when the card opens:
# 2g = ra0 + mt7915.dbdc.b0.dat, 5g = rai0 + mt7915.dbdc.b1.dat. Calibration comes from /mnt/vendor/nvcfg/e2p.
# The profiles are rendered from the stock files (saved once as *.stock) with only the keys below changed.

[ -n "$INCLUDE_ONLY" ] || {
	. /lib/netifd/netifd-wireless.sh
	init_wireless_driver "$@"
}

MTWIFI_DIR=${MTWIFI_DIR:-/etc/wireless/mediatek}
MTWIFI_REGIONS=${MTWIFI_REGIONS:-/usr/share/x28-wifi/regions}
MTWIFI_CHANNELS5=${MTWIFI_CHANNELS5:-/usr/share/x28-wifi/channels5}
MTWIFI_L1=${MTWIFI_L1:-/etc/wireless/l1profile.dat}
MTWIFI_RUN=${MTWIFI_RUN:-/var/run/mtwifi}
MTWIFI_SCAN_DIR=${MTWIFI_SCAN_DIR:-/tmp}
# Networks per band. mt_wifi creates ra1..ra3 / rai1..rai3 only when it loads, from BssidNum in the profile, so x28-wifi-l1 sets this
# value in the stock profiles at boot; keep the two in step.
MTWIFI_MAXBSS=${MTWIFI_MAXBSS:-4}

# mtwifi_band <band> <radio section>: prints the band's main interface and profile, e.g. "rai0 .../mt7915.dbdc.b1.dat".
# LuCI's frequency widget needs iwinfo, which mt_wifi lacks, so saving a radio there deletes band, channel and htmode
# (observed); an empty band falls back to the section name `wifi config` gave the radio (radio_2g, radio_5g).
mtwifi_band() {
	case "${1:-$2}" in
		2g|*_2g) echo "ra0 $MTWIFI_DIR/mt7915.dbdc.b0.dat" ;;
		5g|*_5g) echo "rai0 $MTWIFI_DIR/mt7915.dbdc.b1.dat" ;;
		*) return 1 ;;
	esac
}

# Prints the hardware-capability keys of a board whose Wi-Fi is two separate MT7915 chips, one per band (l1profile.dat lists two cards:
# INDEX0 and INDEX1; a single combined chip lists one). The stock profile in the ROM is the single-chip template (DBDC_MODE=1, 2 streams);
# with two chips it makes the 5 GHz firmware assert when its network starts (FWCmdTimeout, a 30 s stall of the network stack, no 5 GHz). The vendor
# firmware's own lan_mgr writes these values for such a board. Prints nothing for a single-chip board.
mtwifi_caps() {
	local cards
	cards="$(grep -c '^INDEX[0-9]*=' "$MTWIFI_L1" 2>/dev/null)"
	[ "${cards:-0}" -ge 2 ] || return 0
	echo "DBDC_MODE=0 HT_TxStream=4 HT_RxStream=4 MaxDLMuMimo=4 MaxULMuMimo=4 MaxRuOfdma=16 Disable160RuMu=0x38 PERCENTAGEenable=1"
}

# mtwifi_render <profile> KEY=value...: rewrite those keys in a fresh copy of the stock profile.
mtwifi_render() {
	local dat="$1" kv key value
	shift
	[ -f "$dat.stock" ] || cp "$dat" "$dat.stock" || return 1
	cp "$dat.stock" "$dat.new" || return 1
	for kv in "$@"; do
		key="${kv%%=*}"
		value="$(printf '%s' "${kv#*=}" | sed 's/[\\&|]/\\&/g')"
		grep -q "^$key=" "$dat.new" || echo "$key=" >> "$dat.new"
		sed "s|^$key=.*|$key=$value|" "$dat.new" > "$dat.tmp" && mv "$dat.tmp" "$dat.new" || return 1
	done
	mv "$dat.new" "$dat"
}

# Prints "AuthMode EncrypType" for an OpenWrt encryption value; fails for unsupported ones.
mtwifi_auth() {
	case "$1" in
		none|'') echo "OPEN NONE" ;;
		psk2|psk2+ccmp|psk2+aes) echo "WPA2PSK AES" ;;
		psk-mixed*) echo "WPAPSKWPA2PSK AES" ;;
		sae|sae+ccmp) echo "WPA3PSK AES" ;;
		sae-mixed*) echo "WPA2PSKWPA3PSK AES" ;;
		*) return 1 ;;
	esac
}

# Prints WHNAT=0|1 for the radio's whnat option, nothing when unset (the stock profile's 1 stays). WHNAT is the vendor's Wi-Fi
# offload engine (WED): 1 makes mtk_warp allocate about 50 MiB of packet buffers for this radio (TX 16384 x 1900 B, RX 12288 x 1700 B),
# measured on the unit as about 70 MiB per radio with the rings; 0 frees them and sends the traffic through the CPU.
mtwifi_whnat() {
	case "$1" in 0|1) echo "WHNAT=$1" ;; esac
}

# mtwifi_perf <ifname>: the vendor's "Performance Mode" for one radio, what its lan_mgr (mtkt750_lan_mgr_wifi_performance_mode) writes
# into the Wi-Fi start script when SYS_WLAN_PERFORMANCE_MODE_SW is 1: clear-channel assessment on, smart carrier sense off, TX burst
# off and two MAC registers of the radio. The driver forgets them when the card is reopened, so unsetting the option and restarting
# Wi-Fi is the undo. Not measured for speed yet; see #583.
mtwifi_perf() {
	local ifn="$1" iw="${MTWIFI_IWPRIV:-iwpriv}" r1 r2
	case "$ifn" in
		ra0) r1=820E4014 r2=820E31A4 ;;
		rai0) r1=820F401C r2=820F31B4 ;;
		*) return 1 ;;
	esac
	"$iw" "$ifn" set EDCCAEnable=1 && "$iw" "$ifn" set SCSEnable=0 && "$iw" "$ifn" set TxBurst=0 &&
		"$iw" "$ifn" mac "$r1=ffff0000" && "$iw" "$ifn" mac "$r2=00020101"
}

# Prints "PMFMFPC PMFMFPR" for ieee80211w (0 off, 1 optional, 2 required); unset keeps the stock profile's 1 0.
mtwifi_pmf() {
	case "$1" in
		0) echo "0 0" ;;
		2) echo "1 1" ;;
		*) echo "1 0" ;;
	esac
}

# Prints the AccessPolicy for a macfilter value: 1 allow listed only, 2 deny listed, 0 off.
mtwifi_policy() {
	case "$1" in
		allow) echo 1 ;;
		deny) echo 2 ;;
		*) echo 0 ;;
	esac
}

# Prints "HT_BW VHT_BW" for an htmode.
mtwifi_bw() {
	case "$1" in
		*20) echo "0 0" ;;
		*40) echo "1 0" ;;
		*160) echo "1 2" ;;
		*) echo "1 1" ;;
	esac
}

# Prints "code CountryRegion CountryRegionABand" for a country; an unknown one gets US, so a bad value can't take Wi-Fi down.
mtwifi_country() {
	grep "^${1:-US} " "$MTWIFI_REGIONS" || grep '^US ' "$MTWIFI_REGIONS" || echo "US 0 9"
}

# mtwifi_channel <band ifname> <channel> <CountryRegion> <CountryRegionABand>: the channel to use. The driver doesn't enforce
# the region itself (observed: Iran's region stayed on 36 with Channel=0 or 36), so "auto" or a channel the country doesn't
# allow becomes the region's first one.
mtwifi_channel() {
	local list c
	if [ "$1" = ra0 ]; then
		list="1 2 3 4 5 6 7 8 9 10 11"
		[ "$3" != 1 ] || list="$list 12 13"
	else
		list="$(sed -n "s/^$4 //p" "$MTWIFI_CHANNELS5")"
		[ -n "$list" ] || list=36
	fi
	for c in $list; do
		[ "$c" != "$2" ] || { echo "$c"; return; }
	done
	echo "${list%% *}"
}

drv_mtwifi_init_device_config() {
	config_add_string country
	config_add_int txpower_pct beacon_int whnat performance
}

drv_mtwifi_init_iface_config() {
	config_add_boolean hidden isolate wmm
	config_add_int dtim_period
	config_add_string macfilter ieee80211w bssid
	config_add_array maclist
}

drv_mtwifi_cleanup() {
	:
}

# Validate all interfaces before closing the card; netifd's iterator does not propagate callback failures.
mtwifi_check_vif() {
	local mode ssid encryption key bssid auth
	json_select config
	json_get_vars mode ssid encryption key bssid
	json_select ..
	case "$mode" in
		ap) checked_ap=$((${checked_ap:-0} + 1)); [ "$checked_ap" -le "$MTWIFI_MAXBSS" ] || setup_error=TOO_MANY_APS ;;
		sta) [ -z "$checked_sta" ] || setup_error=TOO_MANY_CLIENTS; checked_sta=1 ;;
		*) setup_error=UNSUPPORTED_MODE ;;
	esac
	[ -n "$ssid" ] && [ "${#ssid}" -le 32 ] || setup_error=INVALID_SSID
	# A newline would inject another key into the driver's line-based profile.
	case "$ssid$key" in *'
'*|*"$(printf '\r')"*) setup_error=INVALID_CONFIG ;; esac
	auth="$(mtwifi_auth "$encryption")" || setup_error=INVALID_ENCRYPTION
	case "$auth" in OPEN*) ;; *)
		[ "${#key}" -ge 8 ] && [ "${#key}" -le 63 ] || setup_error=INVALID_KEY ;;
	esac
	[ -z "$bssid" ] || printf '%s\n' "$bssid" | grep -Eq '^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$' || setup_error=INVALID_BSSID
}

mtwifi_apcli() {
	case "$1" in ra0) echo apcli0 ;; rai0) echo apclii0 ;; *) return 1 ;; esac
}

mtwifi_setup_sta() {
	local encryption ieee80211w
	json_select config
	json_get_vars encryption ieee80211w
	json_get_var sta_ssid ssid
	json_get_var sta_key key
	json_get_var sta_bssid bssid
	json_select ..
	sta_name="$1" sta_auth="$(mtwifi_auth "$encryption")"
	case "$encryption" in
		sae|sae+ccmp) sta_pmf="1 1" ;;
		sae-mixed*) sta_pmf="1 0" ;;
		*) sta_pmf="$(mtwifi_pmf "${ieee80211w:-0}")" ;;
	esac
}

# Firmware handles authentication and reconnects; netifd owns the resulting interface and its network.
mtwifi_connect() {
	local ifn="$1" auth cipher mfpc mfpr
	set -- $sta_auth $sta_pmf
	auth="$1" cipher="$2" mfpc="$3" mfpr="$4"
	ip link set dev "$ifn" up &&
	iwpriv "$ifn" set ApCliEnable=0 &&
	iwpriv "$ifn" set "ApCliAuthMode=$auth" &&
	iwpriv "$ifn" set "ApCliEncrypType=$cipher" &&
	iwpriv "$ifn" set "ApCliPMFMFPC=$mfpc" &&
	iwpriv "$ifn" set "ApCliPMFMFPR=$mfpr" &&
	iwpriv "$ifn" set "ApCliSsid=$sta_ssid" &&
	{ [ "$auth" = OPEN ] || iwpriv "$ifn" set "ApCliWPAPSK=$sta_key"; } &&
	iwpriv "$ifn" set "ApCliBssid=${sta_bssid:-00:00:00:00:00:00}" &&
	iwpriv "$ifn" set ApCliEnable=1
}

# Reopening the DBDC card resets both clients. Keep only active credentials in root-only RAM, never source them as shell.
mtwifi_reconnect() {
	local sta_ssid sta_key sta_bssid sta_auth sta_pmf
	[ -f "$MTWIFI_RUN/$1" ] || return 0
	{
		IFS= read -r sta_ssid && IFS= read -r sta_key && IFS= read -r sta_bssid &&
		IFS= read -r sta_auth && IFS= read -r sta_pmf
	} < "$MTWIFI_RUN/$1" || return 1
	mtwifi_connect "$1"
}

# Called per AP interface: records network number vif_n as vif_<field>_<n> (up to MTWIFI_MAXBSS per band).
mtwifi_setup_vif() {
	local ssid encryption key hidden isolate wmm dtim_period macfilter ieee80211w maclist auth pmf policy acl i
	json_select config
	json_get_vars ssid encryption key hidden isolate wmm dtim_period macfilter ieee80211w
	json_get_values maclist maclist
	json_select ..
	auth="$(mtwifi_auth "$encryption")" || { wireless_setup_failed INVALID_ENCRYPTION; return 1; }
	case "$auth" in OPEN*) key= ;; *) [ "${#key}" -ge 8 ] && [ "${#key}" -le 63 ] || { wireless_setup_failed INVALID_KEY; return 1; } ;; esac
	pmf="$(mtwifi_pmf "$ieee80211w")" policy="$(mtwifi_policy "$macfilter")" acl="$(echo $maclist | tr ' ' ';')"
	i=$vif_n; vif_n=$((vif_n + 1))
	[ "$i" != 0 ] || vif_dtim="${dtim_period:-1}"
	eval "vif_name_$i=\$1 vif_ssid_$i=\$ssid vif_key_$i=\$key vif_auth_$i=\$auth vif_hide_$i=\${hidden:-0} vif_iso_$i=\${isolate:-0}" \
		"vif_wmm_$i=\${wmm:-1} vif_pmf_$i=\$pmf vif_pol_$i=\$policy vif_acl_$i=\$acl"
}

mtwifi_setup() {
	local channel htmode country band txpower_pct beacon_int whnat performance ifname dat rai0_up cc base k ap_n htbw vhtbw ccode creg cab
	local ssid key auth hide iso wmm pmf pol acl lauth= lenc= lhide= liso= lwmm= lpmfc= lpmfr=
	local vif_n=0 vif_dtim=1
	local sta_name= sta_ssid= sta_key= sta_bssid= sta_auth="OPEN NONE" sta_pmf= apcli
	local checked_ap= checked_sta= setup_error=
	json_select config
	json_get_vars channel htmode country band txpower_pct beacon_int whnat performance
	json_select ..
	set -- $(mtwifi_band "$band" "$interface")
	[ "$#" = 2 ] || { wireless_setup_failed INVALID_BAND; return 1; }
	ifname="$1" dat="$2"
	[ -f "$dat" ] || [ -f "$dat.stock" ] || { wireless_setup_failed MISSING_PROFILE; return 1; }
	for_each_interface "" mtwifi_check_vif
	[ -z "$setup_error" ] || { wireless_setup_failed "$setup_error"; return 1; }
	for_each_interface "ap" mtwifi_setup_vif
	for_each_interface "sta" mtwifi_setup_sta
	apcli="$(mtwifi_apcli "$ifname")"
	# The vendor client stalls when HT40's secondary channel differs from the upstream AP (#633).
	[ -z "$sta_name" ] || [ "$ifname" != ra0 ] || htmode=HT20
	# Every network on this band disabled. RadioOn=0 does not switch one band of the DBDC card off (observed: ra0 then
	# beaconed an open "HT_AP0"), and ra0 must stay up while rai0 is. So such a band gets a hidden WPA2 network with a
	# random, never stored key, and its interface stays up only when ra0 has to carry rai0.
	ap_n=$vif_n
	[ "$ap_n" -gt 0 ] || {
		vif_n=1 vif_name_0= vif_ssid_0="x28-off" vif_hide_0=1 vif_auth_0="WPA2PSK AES" vif_iso_0=0 vif_wmm_0=1 vif_pmf_0="1 0" vif_pol_0=0 vif_acl_0=
		vif_key_0="$(head -c 24 /dev/urandom | hexdump -ve '1/1 "%02x"')"
	}
	# The merged profile takes CountryCode and CountryRegion from the 5 GHz one (multi_profile.c), so LuCI sets both radios.
	cc="$(mtwifi_country "$country")"
	set -- $(mtwifi_bw "$htmode") $cc
	htbw=$1 vhtbw=$2 ccode=$3 creg=$4 cab=$5
	channel="$(mtwifi_channel "$ifname" "$channel" "$creg" "$cab")"
	base="${ifname%0}"
	# The driver merges both profiles into DBDC_card0.dat and reads it only when the card opens, i.e. with ra0 and
	# rai0 both down (observed: bouncing ra0 alone left 2.4 GHz on its old key). Close both, reopen what was up.
	rm -f "$MTWIFI_RUN/$apcli"
	rai0_up="$(ip link show dev rai0 up 2>/dev/null)"
	ip link set dev rai0 down 2>/dev/null
	ip link set dev ra0 down 2>/dev/null
	# The survey table disappears with the card; its age marker must not suppress the next scan.
	rm -f "$MTWIFI_SCAN_DIR/mtwifi-scan-ra0" "$MTWIFI_SCAN_DIR/mtwifi-scan-rai0"
	set -- "HT_BW=$htbw" "VHT_BW=$vhtbw" "Channel=$channel" "CountryCode=$ccode" "CountryRegion=$creg" "CountryRegionABand=$cab" \
		"DtimPeriod=$vif_dtim" "TxPower=${txpower_pct:-100}" "ApCliEnable=0" "ApCliAuthMode=${sta_auth%% *}" \
		"ApCliEncrypType=${sta_auth#* }" "BeaconPeriod=${beacon_int:-100}"
	# Per-network keys: one SSID<n>/WPAPSK<n>/AccessPolicy<n-1> each, and ';' lists (one entry per network) for the rest.
	k=0
	while [ "$k" -lt "$vif_n" ]; do
		eval "ssid=\$vif_ssid_$k key=\$vif_key_$k auth=\$vif_auth_$k hide=\$vif_hide_$k iso=\$vif_iso_$k wmm=\$vif_wmm_$k pmf=\$vif_pmf_$k pol=\$vif_pol_$k acl=\$vif_acl_$k"
		set -- "$@" "SSID$((k + 1))=$ssid" "WPAPSK$((k + 1))=$key" "AccessPolicy$k=$pol" "AccessControlList$k=$acl"
		lauth="$lauth${lauth:+;}${auth%% *}" lenc="$lenc${lenc:+;}${auth#* }" lhide="$lhide${lhide:+;}$hide" liso="$liso${liso:+;}$iso"
		lwmm="$lwmm${lwmm:+;}$wmm" lpmfc="$lpmfc${lpmfc:+;}${pmf%% *}" lpmfr="$lpmfr${lpmfr:+;}${pmf#* }"
		k=$((k + 1))
	done
	mtwifi_render "$dat" "$@" "AuthMode=$lauth" "EncrypType=$lenc" "HideSSID=$lhide" "NoForwarding=$liso" "WmmCapable=$lwmm" \
		"PMFMFPC=$lpmfc" "PMFMFPR=$lpmfr" $(mtwifi_whnat "$whnat") $(mtwifi_caps) || { wireless_setup_failed PROFILE_WRITE; return 1; }
	# The driver registers rai0 as a virtual interface of ra0: it only opens while ra0 is up (observed), and netifd
	# sets up both radios at once; with 2g disabled ra0 then carries the hidden, locked network above.
	[ "$ifname" = ra0 ] || ip link set dev ra0 up 2>/dev/null
	if [ "$ap_n" -gt 0 ] || [ -n "$sta_name" ] || { [ "$ifname" = ra0 ] && [ -n "$rai0_up" ]; }; then
		ip link set dev "$ifname" up || { wireless_setup_failed IFUP_FAILED; return 1; }
	fi
	[ "$ifname" = rai0 ] || [ -z "$rai0_up" ] || ip link set dev rai0 up 2>/dev/null
	# Networks 2..n are ra1.. / rai1..; the rest of the driver's fixed slots stay down.
	k=1
	while [ "$k" -lt "$MTWIFI_MAXBSS" ]; do
		if [ "$k" -lt "$ap_n" ]; then
			ip link set dev "$base$k" up || { wireless_setup_failed MULTI_SSID_UNAVAILABLE; return 1; }
		else
			ip link set dev "$base$k" down 2>/dev/null
		fi
		k=$((k + 1))
	done
	case "$apcli" in
		apcli0) [ -z "$rai0_up" ] || mtwifi_reconnect apclii0 || { wireless_setup_failed CLIENT_RECONNECT_FAILED; return 1; } ;;
		apclii0) mtwifi_reconnect apcli0 || { wireless_setup_failed CLIENT_RECONNECT_FAILED; return 1; } ;;
	esac
	# Performance mode needs the interface up; a failure is logged, never fatal (Wi-Fi works without it).
	if [ "$performance" = 1 ]; then
		mtwifi_perf "$ifname" >/dev/null 2>&1 || logger -t mtwifi "performance mode not applied on $ifname"
	fi
	if [ -n "$sta_name" ]; then
		mtwifi_connect "$apcli" || {
			iwpriv "$apcli" set ApCliEnable=0 2>/dev/null
			ip link set dev "$apcli" down 2>/dev/null
			wireless_setup_failed CLIENT_SETUP_FAILED
			return 1
		}
		(umask 077; mkdir -p "$MTWIFI_RUN" && chmod 700 "$MTWIFI_RUN" &&
			printf '%s\n' "$sta_ssid" "$sta_key" "$sta_bssid" "$sta_auth" "$sta_pmf" > "$MTWIFI_RUN/$apcli.new" &&
			mv "$MTWIFI_RUN/$apcli.new" "$MTWIFI_RUN/$apcli") || {
			iwpriv "$apcli" set ApCliEnable=0 2>/dev/null
			ip link set dev "$apcli" down 2>/dev/null
			wireless_setup_failed CLIENT_STATE_FAILED; return 1
		}
		wireless_add_vif "$sta_name" "$apcli"
	else
		rm -f "$MTWIFI_RUN/$apcli"
		ip link set dev "$apcli" down 2>/dev/null
	fi
	k=0
	while [ "$k" -lt "$ap_n" ]; do
		eval "ssid=\$vif_name_$k"
		wireless_add_vif "$ssid" "$base$k"
		k=$((k + 1))
	done
	wireless_set_up
}

mtwifi_teardown() {
	local band apcli k
	json_select config
	json_get_vars band
	json_select ..
	set -- $(mtwifi_band "$band" "$interface")
	[ "$#" = 2 ] || return 0
	apcli="$(mtwifi_apcli "$1")"
	rm -f "$MTWIFI_RUN/$apcli"
	iwpriv "$apcli" set ApCliEnable=0 2>/dev/null
	ip link set dev "$apcli" down 2>/dev/null
	k=$((MTWIFI_MAXBSS - 1))
	while [ "$k" -ge 1 ]; do ip link set dev "${1%0}$k" down 2>/dev/null; k=$((k - 1)); done
	ip link set dev "$1" down 2>/dev/null
}

# netifd starts the two radios separately, but profile reloads close the same card.
drv_mtwifi_setup() (
	flock -x 9 || { wireless_setup_failed RADIO_BUSY; exit 1; }
	mtwifi_setup
) 9>"${MTWIFI_LOCK:-/var/lock/mtwifi.lock}"

drv_mtwifi_teardown() (
	flock -x 9 || return 1
	mtwifi_teardown
) 9>"${MTWIFI_LOCK:-/var/lock/mtwifi.lock}"

[ -n "$INCLUDE_ONLY" ] || add_driver mtwifi
