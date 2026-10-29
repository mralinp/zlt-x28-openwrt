#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# netifd wireless handler for the X28's MT7915 DBDC on MediaTek's mt_wifi driver (no nl80211). The driver reads
# /etc/wireless/l1profile.dat and one .dat profile per band whenever the band's main interface comes up:
# 2g = ra0 + mt7915.dbdc.b0.dat, 5g = rai0 + mt7915.dbdc.b1.dat. Calibration comes from /mnt/vendor/nvcfg/e2p.
# The profiles are rendered from the stock files (saved once as *.stock) with only the keys below changed.

[ -n "$INCLUDE_ONLY" ] || {
	. /lib/netifd/netifd-wireless.sh
	init_wireless_driver "$@"
}

MTWIFI_DIR=${MTWIFI_DIR:-/etc/wireless/mediatek}

# Prints the band's main interface and profile, e.g. "rai0 /etc/wireless/mediatek/mt7915.dbdc.b1.dat".
mtwifi_band() {
	case "$1" in
		2g) echo "ra0 $MTWIFI_DIR/mt7915.dbdc.b0.dat" ;;
		5g) echo "rai0 $MTWIFI_DIR/mt7915.dbdc.b1.dat" ;;
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
}

drv_mtwifi_init_iface_config() {
	config_add_boolean hidden isolate
}

drv_mtwifi_cleanup() {
	:
}

# Called per AP interface; fills the caller's (drv_mtwifi_setup) vif_* from the first one.
mtwifi_setup_vif() {
	local ssid encryption key hidden isolate
	[ -z "$vif_name" ] || return 0  # shortcut: one BSS per band (BssidNum=1); MBSS needs ra1/rai1 and BssidNum.
	json_select config
	json_get_vars ssid encryption key hidden isolate
	json_select ..
	vif_auth="$(mtwifi_auth "$encryption")" || { wireless_setup_failed INVALID_ENCRYPTION; return 1; }
	case "$vif_auth" in OPEN*) key= ;; *) [ "${#key}" -ge 8 ] && [ "${#key}" -le 63 ] || { wireless_setup_failed INVALID_KEY; return 1; } ;; esac
	vif_name="$1" vif_ssid="$ssid" vif_key="$key" vif_hidden="${hidden:-0}" vif_isolate="${isolate:-0}"
}

drv_mtwifi_setup() {
	local channel htmode country band ifname dat vif_name= vif_auth vif_ssid vif_key vif_hidden vif_isolate
	json_select config
	json_get_vars channel htmode country band
	json_select ..
	set -- $(mtwifi_band "$band")
	[ "$#" = 2 ] || { wireless_setup_failed INVALID_BAND; return 1; }
	ifname="$1" dat="$2"
	[ -f "$dat" ] || [ -f "$dat.stock" ] || { wireless_setup_failed MISSING_PROFILE; return 1; }
	for_each_interface "ap" mtwifi_setup_vif
	[ -n "$vif_name" ] || { wireless_setup_failed NO_AP; return 1; }
	set -- $vif_auth $(mtwifi_bw "$htmode")
	ip link set dev "$ifname" down 2>/dev/null
	mtwifi_render "$dat" "SSID1=$vif_ssid" "AuthMode=$1" "EncrypType=$2" "WPAPSK1=$vif_key" "HideSSID=$vif_hidden" \
		"NoForwarding=$vif_isolate" "Channel=${channel:-0}" "CountryCode=${country:-US}" "HT_BW=$3" "VHT_BW=$4" ||
		{ wireless_setup_failed PROFILE_WRITE; return 1; }
	ip link set dev "$ifname" up || { wireless_setup_failed IFUP_FAILED; return 1; }
	wireless_add_vif "$vif_name" "$ifname"
	wireless_set_up
}

drv_mtwifi_teardown() {
	local band
	json_select config
	json_get_vars band
	json_select ..
	set -- $(mtwifi_band "$band")
	[ "$#" = 2 ] && ip link set dev "$1" down 2>/dev/null
}

[ -n "$INCLUDE_ONLY" ] || add_driver mtwifi
