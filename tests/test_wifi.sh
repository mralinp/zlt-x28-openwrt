#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Profile rendering and option mapping of the mtwifi netifd handler; no driver or netifd involved.
set -e
dir=$(mktemp -d); trap 'rm -rf "$dir"' EXIT
INCLUDE_ONLY=1 MTWIFI_DIR=$dir MTWIFI_REGIONS=$(dirname "$0")/../package/x28-wifi/files/regions MTWIFI_CHANNELS5=$(dirname "$0")/../package/x28-wifi/files/channels5 . "$(dirname "$0")/../package/x28-wifi/files/mtwifi.sh"
printf 'Default\nSSID1=old\nAuthMode=OPEN\nWPAPSK1=12345678\nChannel=6\n' > "$dir/p.dat"
mtwifi_render "$dir/p.dat" 'SSID1=My Net & |x\y' AuthMode=WPA2PSK 'WPAPSK1=k&|\ey' HideSSID=1
[ "$(cat "$dir/p.dat")" = "$(printf 'Default\nSSID1=My Net & |x\\y\nAuthMode=WPA2PSK\nWPAPSK1=k&|\\ey\nChannel=6\nHideSSID=1')" ] || { cat "$dir/p.dat"; exit 1; }
grep -q '^SSID1=old$' "$dir/p.dat.stock"
mtwifi_render "$dir/p.dat" SSID1=again
[ "$(grep -c . "$dir/p.dat")" = 5 ] && grep -q '^AuthMode=OPEN$' "$dir/p.dat" || exit 1  # always from the stock copy
[ "$(mtwifi_auth psk2)" = "WPA2PSK AES" ] && [ "$(mtwifi_auth sae-mixed)" = "WPA2PSKWPA3PSK AES" ] && [ "$(mtwifi_auth none)" = "OPEN NONE" ] || exit 1
mtwifi_auth wep-open && exit 1
[ "$(mtwifi_bw HT20)" = "0 0" ] && [ "$(mtwifi_bw HT40)" = "1 0" ] && [ "$(mtwifi_bw HE80)" = "1 1" ] && [ "$(mtwifi_bw VHT160)" = "1 2" ] || exit 1
[ "$(mtwifi_band 5g)" = "rai0 $dir/mt7915.dbdc.b1.dat" ] && ! mtwifi_band 6g || exit 1
[ "$(mtwifi_band '' radio_2g)" = "ra0 $dir/mt7915.dbdc.b0.dat" ] && [ "$(mtwifi_band 2g radio_5g)" = "ra0 $dir/mt7915.dbdc.b0.dat" ] && ! mtwifi_band '' radio0 || exit 1
[ "$(mtwifi_pmf '')" = "1 0" ] && [ "$(mtwifi_pmf 0)" = "0 0" ] && [ "$(mtwifi_pmf 2)" = "1 1" ] || exit 1
[ "$(mtwifi_policy allow)" = 1 ] && [ "$(mtwifi_policy deny)" = 2 ] && [ "$(mtwifi_policy '')" = 0 ] || exit 1
[ "$(mtwifi_country IR)" = "IR 1 4" ] && [ "$(mtwifi_country US)" = "US 0 13" ] && [ "$(mtwifi_country '')" = "US 0 13" ] && [ "$(mtwifi_country XX)" = "US 0 13" ] || exit 1
[ "$(grep -c . "$MTWIFI_REGIONS")" -gt 150 ] && ! grep -qv '^[A-Z][A-Z] [01] [0-9]*$' "$MTWIFI_REGIONS" || exit 1
[ "$(mtwifi_channel rai0 auto 1 4)" = 149 ] && [ "$(mtwifi_channel rai0 36 1 4)" = 149 ] && [ "$(mtwifi_channel rai0 157 1 4)" = 157 ] && [ "$(mtwifi_channel rai0 auto 0 13)" = 36 ] || exit 1
[ "$(mtwifi_channel ra0 auto 1 4)" = 1 ] && [ "$(mtwifi_channel ra0 13 1 4)" = 13 ] && [ "$(mtwifi_channel ra0 13 0 13)" = 1 ] && [ "$(mtwifi_channel ra0 '' 0 13)" = 1 ] && [ "$(mtwifi_channel rai0 36 0 99)" = 36 ] || exit 1
# Every 5 GHz region a country maps to has its channel list.
for r in $(cut -d' ' -f3 "$MTWIFI_REGIONS" | sort -un); do grep -q "^$r " "$MTWIFI_CHANNELS5" || { echo "no channels for region $r"; exit 1; }; done
echo "PASS: mtwifi profile rendering, encryption, bandwidth, band, PMF, MAC-policy and country mapping"
