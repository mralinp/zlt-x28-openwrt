#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Profile rendering and option mapping of the mtwifi netifd handler; no driver or netifd involved.
set -e
dir=$(mktemp -d); trap 'rm -rf "$dir"' EXIT
INCLUDE_ONLY=1 MTWIFI_DIR=$dir . "$(dirname "$0")/../package/x28-wifi/files/mtwifi.sh"
printf 'Default\nSSID1=old\nAuthMode=OPEN\nWPAPSK1=12345678\nChannel=6\n' > "$dir/p.dat"
mtwifi_render "$dir/p.dat" 'SSID1=My Net & |x\y' AuthMode=WPA2PSK 'WPAPSK1=k&|\ey' HideSSID=1
[ "$(cat "$dir/p.dat")" = "$(printf 'Default\nSSID1=My Net & |x\\y\nAuthMode=WPA2PSK\nWPAPSK1=k&|\\ey\nChannel=6\nHideSSID=1')" ] || { cat "$dir/p.dat"; exit 1; }
grep -q '^SSID1=old$' "$dir/p.dat.stock"
mtwifi_render "$dir/p.dat" SSID1=again
[ "$(grep -c . "$dir/p.dat")" = 5 ] && grep -q '^AuthMode=OPEN$' "$dir/p.dat"  # always from the stock copy
[ "$(mtwifi_auth psk2)" = "WPA2PSK AES" ] && [ "$(mtwifi_auth sae-mixed)" = "WPA2PSKWPA3PSK AES" ] && [ "$(mtwifi_auth none)" = "OPEN NONE" ]
! mtwifi_auth wep-open
[ "$(mtwifi_bw HT20)" = "0 0" ] && [ "$(mtwifi_bw HT40)" = "1 0" ] && [ "$(mtwifi_bw HE80)" = "1 1" ] && [ "$(mtwifi_bw VHT160)" = "1 2" ]
[ "$(mtwifi_band 5g)" = "rai0 $dir/mt7915.dbdc.b1.dat" ] && ! mtwifi_band 6g
echo "PASS: mtwifi profile rendering, encryption, bandwidth and band mapping"
