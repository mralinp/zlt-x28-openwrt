#!/bin/sh
# netifd lifecycle with fake hardware commands; profile rendering is real.
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
INCLUDE_ONLY=1 . "$root/package/x28-wifi/files/mtwifi.sh"
MTWIFI_DIR=$t MTWIFI_L1=$t/missing MTWIFI_RUN=$t/run MTWIFI_LOCK=$t/radio.lock MTWIFI_SCAN_DIR=$t
MTWIFI_REGIONS=$root/package/x28-wifi/files/regions
MTWIFI_CHANNELS5=$root/package/x28-wifi/files/channels5
calls=$t/calls
flock() { [ "$*" = '-x 9' ]; }
ip() { printf 'ip %s\n' "$*" >> "$calls"; }
iwpriv() { printf 'iwpriv %s\n' "$*" >> "$calls"; [ "${fail_iw:-}" != "$*" ]; }
wireless_add_vif() { printf 'vif %s\n' "$*" >> "$calls"; }
wireless_set_up() { echo up >> "$calls"; }
wireless_setup_failed() { errors="$errors $1"; }
json_select() { :; }
json_get_vars() { for var in "$@"; do eval "$var=\${${section}_${var}-}"; done; }
json_get_var() { eval "$1=\${${section}_${2}-}"; }
json_get_values() { eval "$1="; }
for_each_interface() {
    types=$1; callback=$2
    for section in $sections; do
        eval "mode=\${${section}_mode}"
        case " $types " in *" $mode "*|'  ') "$callback" "$section" ;; esac
    done
    section=radio
}
reset() {
    rm -rf "$t/run"
    : > "$calls"; errors=; fail_iw=; section=radio; sections='client'; interface=radio_2g
    radio_band=2g radio_channel=6 radio_country=US radio_htmode=HT40
    client_mode=sta client_ssid='Home network' client_encryption=sae client_key='password123'
    client_bssid=02:00:00:aa:bb:cc client_ieee80211w=
    for band in 0 1; do printf 'Default\nSSID1=old\nApCliEnable=1\n' > "$t/mt7915.dbdc.b$band.dat"; done
}
fail() { echo "FAIL: $*" >&2; exit 1; }
reset
touch "$t/mtwifi-scan-ra0" "$t/mtwifi-scan-rai0"
drv_mtwifi_setup
[ ! -e "$t/mtwifi-scan-ra0" ] && [ ! -e "$t/mtwifi-scan-rai0" ] || fail 'stale scan cache survived card reopen'
[ -z "$errors" ] || fail "$errors"
grep -qx 'vif client apcli0' "$calls" || fail 'STA not registered with netifd'
grep -qx 'iwpriv apcli0 set ApCliSsid=Home network' "$calls" || fail 'SSID'
grep -qx 'iwpriv apcli0 set ApCliAuthMode=WPA3PSK' "$calls" || fail 'SAE'
grep -qx 'iwpriv apcli0 set ApCliPMFMFPR=1' "$calls" || fail 'SAE must require PMF'
grep -qx 'iwpriv apcli0 set ApCliBssid=02:00:00:aa:bb:cc' "$calls" || fail 'BSSID'
grep -qx 'HT_BW=0' "$t/mt7915.dbdc.b0.dat" || fail '2g STA must avoid HT40 mismatch'
grep -qx 'ApCliEnable=0' "$t/mt7915.dbdc.b0.dat" || fail 'profile must not auto-connect'
grep -qx 'ApCliAuthMode=WPA3PSK' "$t/mt7915.dbdc.b0.dat" || fail 'iwinfo missing SAE profile status'
grep -qx 'ApCliEncrypType=AES' "$t/mt7915.dbdc.b0.dat" || fail 'iwinfo missing client cipher status'
reset
interface=radio_5g radio_band=5g radio_channel=36 radio_htmode=HE80
client_encryption=psk2 client_bssid=
drv_mtwifi_setup
grep -qx 'vif client apclii0' "$calls" || fail '5g STA mapping'
grep -qx 'iwpriv apclii0 set ApCliBssid=00:00:00:00:00:00' "$calls" || fail 'stale BSSID not cleared'
grep -qx 'VHT_BW=1' "$t/mt7915.dbdc.b1.dat" || fail '5g bandwidth changed'
grep -qx 'ApCliAuthMode=WPA2PSK' "$t/mt7915.dbdc.b1.dat" || fail 'iwinfo missing WPA2 profile status'
drv_mtwifi_teardown
grep -qx 'iwpriv apclii0 set ApCliEnable=0' "$calls" || fail 'teardown left client connected'
[ "$(ls -ld "$MTWIFI_RUN" | cut -c1-10)" = drwx------ ] || fail 'credential directory permissions'
reset
client_ssid='bad
SSID'
drv_mtwifi_setup && fail 'profile newline accepted'
reset
client_key="$(printf 'bad\rpassword')"
drv_mtwifi_setup && fail 'profile carriage return accepted'
reset
client_key=short
drv_mtwifi_setup && fail 'invalid key accepted'
[ ! -s "$calls" ] || fail 'invalid config changed hardware'
reset
client_bssid='bad; bssid'
drv_mtwifi_setup && fail 'invalid BSSID accepted'
reset
sections='client other'; other_mode=sta other_ssid=Other other_encryption=none
drv_mtwifi_setup && fail 'second client silently ignored'
reset
sections='client'; client_mode=adhoc
drv_mtwifi_setup && fail 'unsupported mode silently ignored'
reset
fail_iw='apcli0 set ApCliEnable=1'
drv_mtwifi_setup && fail 'connection command failure ignored'
grep -q '^up$' "$calls" && fail 'failed radio reported up'
grep -qx 'iwpriv apcli0 set ApCliEnable=0' "$calls" || fail 'failed client not stopped'
reset
sections='ap client'; ap_mode=ap ap_ssid=Local ap_encryption=psk2 ap_key=password123
drv_mtwifi_setup
grep -qx 'vif ap ra0' "$calls" && grep -qx 'vif client apcli0' "$calls" || fail 'AP + STA'
reset
client_encryption=none client_key=
drv_mtwifi_setup
grep -qx 'iwpriv apcli0 set ApCliAuthMode=OPEN' "$calls" || fail 'open network'
grep -qx 'ApCliAuthMode=OPEN' "$t/mt7915.dbdc.b0.dat" || fail 'iwinfo retained encrypted profile status'
grep -qx 'ApCliEncrypType=NONE' "$t/mt7915.dbdc.b0.dat" || fail 'iwinfo retained client cipher status'
# Reopening the shared card for the other band must reconnect its existing client.
reset
drv_mtwifi_setup
: > "$calls"
interface=radio_5g radio_band=5g radio_channel=36 radio_htmode=HE80
sections=ap; ap_mode=ap ap_ssid=Local ap_encryption=psk2 ap_key=password123
drv_mtwifi_setup
grep -qx 'iwpriv apcli0 set ApCliSsid=Home network' "$calls" || fail 'other band lost its client'
echo 'PASS: mtwifi STA lifecycle, AP coexistence, validation, failure and teardown'
