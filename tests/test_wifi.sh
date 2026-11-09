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
# Two separate chips (two INDEX cards in l1profile.dat) get the vendor's capability keys; one combined chip keeps the stock template.
printf 'Default\nINDEX0=MT7915\nINDEX0_main_ifname=rai0\nINDEX1=MT7915\nINDEX1_main_ifname=ra0\n' > "$dir/l1.two"
printf 'Default\nINDEX0=MT7915D\nINDEX0_main_ifname=ra0;rai0\n' > "$dir/l1.one"
[ "$(MTWIFI_L1=$dir/l1.two mtwifi_caps)" = "DBDC_MODE=0 HT_TxStream=4 HT_RxStream=4 MaxDLMuMimo=4 MaxULMuMimo=4 MaxRuOfdma=16 Disable160RuMu=0x38 PERCENTAGEenable=1" ] || exit 1
[ -z "$(MTWIFI_L1=$dir/l1.one mtwifi_caps)" ] && [ -z "$(MTWIFI_L1=$dir/missing mtwifi_caps)" ] || exit 1
printf 'Default\nDBDC_MODE=1\nHT_TxStream=2\nChannel=36\n' > "$dir/c.dat"
mtwifi_render "$dir/c.dat" Channel=149 $(MTWIFI_L1=$dir/l1.two mtwifi_caps)
grep -q '^DBDC_MODE=0$' "$dir/c.dat" && grep -q '^HT_TxStream=4$' "$dir/c.dat" && grep -q '^Channel=149$' "$dir/c.dat" && grep -q '^MaxRuOfdma=16$' "$dir/c.dat" || { cat "$dir/c.dat"; exit 1; }
# A single-chip board (one PCI network controller) gets the single-card l1profile; two chips keep the PRO's file.
x28l1="$(dirname "$0")/../package/x28-wifi/files/x28-wifi-l1"
mkdir -p "$dir/pci/a" "$dir/pci/b" "$dir/pci/c"; echo 0x060400 > "$dir/pci/a/class"; echo 0x000280 > "$dir/pci/b/class"
cp "$dir/l1.two" "$dir/l1.run"; L1=$dir/l1.run PCI=$dir/pci sh "$x28l1" 2>/dev/null
[ "$(grep -c '^INDEX[0-9]*=' "$dir/l1.run")" = 1 ] && grep -q '^INDEX0=MT7915D$' "$dir/l1.run" || { cat "$dir/l1.run"; exit 1; }
echo 0x028000 > "$dir/pci/c/class"; cp "$dir/l1.two" "$dir/l1.run"; L1=$dir/l1.run PCI=$dir/pci sh "$x28l1" 2>/dev/null
cmp -s "$dir/l1.two" "$dir/l1.run" || exit 1
# Two chips with the original's one-card file (the general image on a PRO, #513) get the PRO's two-card file; a second run keeps it.
cp "$dir/l1.one" "$dir/l1.run"; L1=$dir/l1.run PCI=$dir/pci sh "$x28l1" 2>/dev/null
grep -q '^INDEX0_EEPROM_name=e2p-5g$' "$dir/l1.run" && grep -q '^INDEX1_pcie_slot=0001$' "$dir/l1.run" || { cat "$dir/l1.run"; exit 1; }
cp "$dir/l1.run" "$dir/l1.pro"; L1=$dir/l1.run PCI=$dir/pci sh "$x28l1" 2>/dev/null; cmp -s "$dir/l1.pro" "$dir/l1.run" || exit 1
[ "$(MTWIFI_L1=$dir/l1.run mtwifi_caps)" = "$(MTWIFI_L1=$dir/l1.two mtwifi_caps)" ] || exit 1
# Every 5 GHz region a country maps to has its channel list.
for r in $(cut -d' ' -f3 "$MTWIFI_REGIONS" | sort -un); do grep -q "^$r " "$MTWIFI_CHANNELS5" || { echo "no channels for region $r"; exit 1; }; done
echo "PASS: mtwifi profile rendering, encryption, bandwidth, band, PMF, MAC-policy, country mapping and two-chip capability keys"
