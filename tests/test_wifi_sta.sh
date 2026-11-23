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
wireless_setup_failed() { errors="$errors $1"; echo "$1" >> "$t/errors"; }  # setup runs in a subshell: the file carries the error out
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
    rm -rf "$t/run"; : > "$t/errors"
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
[ ! -s "$t/errors" ] || fail "$(cat "$t/errors")"
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
# Several networks on one band: ra1.. carry networks 2..n, profile lists follow the order, unused slots go down.
reset
sections='a b c'; a_mode=ap a_ssid='Home Net' a_encryption=psk2 a_key=password123 b_mode=ap b_ssid=Guest b_encryption=none c_mode=ap c_ssid=Wpa3 c_encryption=sae c_key=password123 c_hidden=1
drv_mtwifi_setup
[ ! -s "$t/errors" ] || fail "$(cat "$t/errors")"
grep -qx 'vif a ra0' "$calls" && grep -qx 'vif b ra1' "$calls" && grep -qx 'vif c ra2' "$calls" || fail 'networks not mapped to ra0 ra1 ra2'
grep -qx 'ip link set dev ra1 up' "$calls" && grep -qx 'ip link set dev ra2 up' "$calls" && grep -qx 'ip link set dev ra3 down' "$calls" || fail 'slot up/down'
grep -qx 'SSID1=Home Net' "$t/mt7915.dbdc.b0.dat" && grep -qx 'SSID2=Guest' "$t/mt7915.dbdc.b0.dat" && grep -qx 'SSID3=Wpa3' "$t/mt7915.dbdc.b0.dat" || fail 'SSID keys'
grep -qx 'AuthMode=WPA2PSK;OPEN;WPA3PSK' "$t/mt7915.dbdc.b0.dat" && grep -qx 'EncrypType=AES;NONE;AES' "$t/mt7915.dbdc.b0.dat" || fail 'auth lists'
grep -qx 'HideSSID=0;0;1' "$t/mt7915.dbdc.b0.dat" || fail 'hide list'
grep -qx 'WPAPSK3=password123' "$t/mt7915.dbdc.b0.dat" && grep -qx 'AccessPolicy2=0' "$t/mt7915.dbdc.b0.dat" || fail 'per-network keys'
drv_mtwifi_teardown
grep -qx 'ip link set dev ra3 down' "$calls" && grep -qx 'ip link set dev ra1 down' "$calls" || fail 'teardown left slots up'
reset
interface=radio_5g radio_band=5g radio_channel=36 radio_htmode=HE80
sections='a b'; a_mode=ap a_ssid=Five a_encryption=none b_mode=ap b_ssid=Five-2 b_encryption=none
drv_mtwifi_setup
grep -qx 'vif a rai0' "$calls" && grep -qx 'vif b rai1' "$calls" || fail '5g networks not mapped to rai0 rai1'
reset
sections='a b c d e'; for n in a b c d e; do eval "${n}_mode=ap ${n}_ssid=N$n ${n}_encryption=none"; done
drv_mtwifi_setup && fail 'more networks than the driver has slots accepted'
grep -qx TOO_MANY_APS "$t/errors" || fail "wrong error: $(cat "$t/errors")"
reset
sections='a b'; a_mode=ap a_ssid=A a_encryption=none b_mode=ap b_ssid=B b_encryption=none
ip() { printf 'ip %s\n' "$*" >> "$calls"; case "$*" in 'link set dev ra1 up') return 1 ;; esac; }
drv_mtwifi_setup && fail 'a missing ra1 (old profile) must fail, not be ignored'
grep -qx MULTI_SSID_UNAVAILABLE "$t/errors" || fail "wrong error: $(cat "$t/errors")"
ip() { printf 'ip %s\n' "$*" >> "$calls"; }
# The card re-reads the profile only once every interface is down: both clients and the other band's networks
# close first, and the other band's open networks come back.
reset
sections=a; a_mode=ap a_ssid=A a_encryption=none
ip() { printf 'ip %s\n' "$*" >> "$calls"; case "$*" in 'link show dev rai1 up') echo up ;; esac; }
drv_mtwifi_setup
ip() { printf 'ip %s\n' "$*" >> "$calls"; }
for i in apcli0 apclii0 rai1 rai2; do grep -qx "ip link set dev $i down" "$calls" || fail "$i left up while the card reopens"; done
grep -qx 'ip link set dev rai1 up' "$calls" || fail 'other band network not restored'
grep -qx 'ip link set dev rai2 up' "$calls" && fail 'other band slot opened that was down'
# WDS (4-address) is not in this driver build: refused, never run as a plain AP.
reset
sections=a; a_mode=ap a_ssid=A a_encryption=none a_wds=1
drv_mtwifi_setup && fail 'wds accepted'
grep -qx UNSUPPORTED_MODE "$t/errors" || fail "wrong wds error: $(cat "$t/errors")"
unset a_wds
echo 'PASS: mtwifi STA lifecycle, AP coexistence, validation, failure and teardown'
