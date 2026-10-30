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

drv_mtwifi_init_device_config() {
	config_add_string country
	config_add_int txpower_pct beacon_int
}

drv_mtwifi_init_iface_config() {
	config_add_boolean hidden isolate wmm
	config_add_int dtim_period
	config_add_string macfilter ieee80211w
	config_add_array maclist
}

drv_mtwifi_cleanup() {
	:
}

# Called per AP interface; fills the caller's (drv_mtwifi_setup) vif_* from the first one.
mtwifi_setup_vif() {
	local ssid encryption key hidden isolate wmm dtim_period macfilter ieee80211w maclist
	[ -z "$vif_name" ] || return 0  # shortcut: one BSS per band (BssidNum=1); MBSS needs ra1/rai1 and BssidNum.
	json_select config
	json_get_vars ssid encryption key hidden isolate wmm dtim_period macfilter ieee80211w
	json_get_values maclist maclist
	json_select ..
	vif_auth="$(mtwifi_auth "$encryption")" || { wireless_setup_failed INVALID_ENCRYPTION; return 1; }
	case "$vif_auth" in OPEN*) key= ;; *) [ "${#key}" -ge 8 ] && [ "${#key}" -le 63 ] || { wireless_setup_failed INVALID_KEY; return 1; } ;; esac
	vif_name="$1" vif_ssid="$ssid" vif_key="$key" vif_hidden="${hidden:-0}" vif_isolate="${isolate:-0}"
	vif_wmm="${wmm:-1}" vif_dtim="${dtim_period:-1}" vif_pmf="$(mtwifi_pmf "$ieee80211w")"
	vif_policy="$(mtwifi_policy "$macfilter")" vif_acl="$(echo $maclist | tr ' ' ';')"
}

drv_mtwifi_setup() {
	local channel htmode country band txpower_pct beacon_int ifname dat rai0_up
	local vif_name= vif_auth="OPEN NONE" vif_ssid= vif_key= vif_hidden=0 vif_isolate=0 vif_wmm=1 vif_dtim=1
	local vif_pmf="1 0" vif_policy=0 vif_acl=
	json_select config
	json_get_vars channel htmode country band txpower_pct beacon_int
	json_select ..
	set -- $(mtwifi_band "$band" "$interface")
	[ "$#" = 2 ] || { wireless_setup_failed INVALID_BAND; return 1; }
	ifname="$1" dat="$2"
	[ -f "$dat" ] || [ -f "$dat.stock" ] || { wireless_setup_failed MISSING_PROFILE; return 1; }
	for_each_interface "ap" mtwifi_setup_vif
	# Every network on this band disabled. RadioOn=0 does not switch one band of the DBDC card off (observed: ra0 then
	# beaconed an open "HT_AP0"), and ra0 must stay up while rai0 is. So such a band gets a hidden WPA2 network with a
	# random, never stored key, and its interface stays up only when ra0 has to carry rai0.
	[ -n "$vif_name" ] || {
		vif_ssid="x28-off" vif_hidden=1 vif_auth="WPA2PSK AES"
		vif_key="$(head -c 24 /dev/urandom | hexdump -ve '1/1 "%02x"')"
	}
	set -- $vif_auth $(mtwifi_bw "$htmode") $vif_pmf
	[ "$channel" != auto ] || channel=0
	# The driver merges both profiles into DBDC_card0.dat and reads it only when the card opens, i.e. with ra0 and
	# rai0 both down (observed: bouncing ra0 alone left 2.4 GHz on its old key). Close both, reopen what was up.
	rai0_up="$(ip link show dev rai0 up 2>/dev/null)"
	ip link set dev rai0 down 2>/dev/null
	ip link set dev ra0 down 2>/dev/null
	mtwifi_render "$dat" "SSID1=$vif_ssid" "AuthMode=$1" "EncrypType=$2" "WPAPSK1=$vif_key" "HideSSID=$vif_hidden" \
		"NoForwarding=$vif_isolate" "Channel=${channel:-0}" "CountryCode=${country:-US}" "HT_BW=$3" "VHT_BW=$4" \
		"PMFMFPC=$5" "PMFMFPR=$6" "WmmCapable=$vif_wmm" "DtimPeriod=$vif_dtim" "AccessPolicy0=$vif_policy" \
		"AccessControlList0=$vif_acl" "TxPower=${txpower_pct:-100}" "BeaconPeriod=${beacon_int:-100}" ||
		{ wireless_setup_failed PROFILE_WRITE; return 1; }
	# The driver registers rai0 as a virtual interface of ra0: it only opens while ra0 is up (observed), and netifd
	# sets up both radios at once; with 2g disabled ra0 then carries the hidden, locked network above.
	[ "$ifname" = ra0 ] || ip link set dev ra0 up 2>/dev/null
	if [ -n "$vif_name" ] || { [ "$ifname" = ra0 ] && [ -n "$rai0_up" ]; }; then
		ip link set dev "$ifname" up || { wireless_setup_failed IFUP_FAILED; return 1; }
	fi
	[ "$ifname" = rai0 ] || [ -z "$rai0_up" ] || ip link set dev rai0 up 2>/dev/null
	[ -z "$vif_name" ] || wireless_add_vif "$vif_name" "$ifname"
	wireless_set_up
}

drv_mtwifi_teardown() {
	local band
	json_select config
	json_get_vars band
	json_select ..
	set -- $(mtwifi_band "$band" "$interface")
	[ "$#" = 2 ] && ip link set dev "$1" down 2>/dev/null
}

[ -n "$INCLUDE_ONLY" ] || add_driver mtwifi
