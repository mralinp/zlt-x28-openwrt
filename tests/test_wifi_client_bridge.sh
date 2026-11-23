#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
mkdir -p "$t/bin" "$t/net/apcli0" "$t/net/apclii0" "$t/net/br-lan"
ln -s ../br-lan "$t/net/apcli0/master"
cat > "$t/bin/ebtables" <<'SH'
#!/bin/sh
case "$*" in *'-D PREROUTING'*) exit 1 ;; esac
[ -z "${FAIL_EBT:-}" ] || case "$*" in *redirect*) exit 1 ;; esac
printf '%s\n' "$*" >> "$CALLS"
SH
cat > "$t/bin/ip" <<'SH'
#!/bin/sh
[ "$*" = '-4 route show dev br-lan scope link' ] || exit 1
printf '%s\n' '192.168.70.0/24 proto kernel scope link src 192.168.70.1' '10.0.0.0/24 proto static scope link src 10.0.0.1'
SH
printf '#!/bin/sh\n[ "$*" = "-x 9" ]\n' > "$t/bin/flock"
chmod +x "$t/bin/"*
export PATH="$t/bin:$PATH" CALLS="$t/calls" X28_WIFI_SYS="$t/net" X28_WIFI_LOCK="$t/lock"
sh "$root/package/x28-wifi/files/x28-wifi-client"
grep -q -- '-i apcli0 -p IPv4 --ip-dst 192.168.70.0/24 -j RETURN' "$CALLS"
grep -q -- '-i apcli0 -p IPv4 --ip-dst 10.0.0.0/24 -j RETURN' "$CALLS"
grep -q -- '--ip-dst 224.0.0.0/4 -j RETURN' "$CALLS"
grep -q -- '--ip-dst 255.255.255.255 -j RETURN' "$CALLS"
grep -q -- '-i apcli0 -p IPv4 --pkttype-type broadcast -j redirect --redirect-target ACCEPT' "$CALLS"
! grep -q -- '-i apclii0' "$CALLS" # a routed client needs no bridge rules
grep -qx -- '-t nat -A X28_CLIENT -j RETURN' "$CALLS" # unmatched traffic must return to later NAT rules
[ "$(tail -1 "$CALLS")" = '-t nat -A PREROUTING -j X28_CLIENT' ]
: > "$CALLS"; rm "$t/net/apcli0/master"
sh "$root/package/x28-wifi/files/x28-wifi-client"
! grep -q -- '-A PREROUTING' "$CALLS"
# Failed rule installation must never attach a partially populated chain.
ln -s ../br-lan "$t/net/apcli0/master"; : > "$CALLS"
FAIL_EBT=1 sh "$root/package/x28-wifi/files/x28-wifi-client" && exit 1
! grep -q -- '-A PREROUTING' "$CALLS"
# Boot registers the standard fw3 include once; it never rewrites network settings.
. "$root/package/x28-wifi/files/x28-wifi-client.init"
registered=
uci() {
    if [ "$*" = '-q get firewall.x28_wifi_client.path' ]; then
        [ -n "$registered" ] && echo /usr/libexec/x28-wifi-client
    else
        cat >> "$t/uci"; registered=1
    fi
}
start; start
[ "$(grep -c '^commit firewall$' "$t/uci")" = 1 ]
grep -q "set firewall.x28_wifi_client.reload='1'" "$t/uci"
echo 'PASS: bridged STA redirect, subnet and multicast exemptions, routed STA unchanged'
