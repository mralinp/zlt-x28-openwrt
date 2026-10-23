#!/bin/sh
set -eu
backup=${1:-/root/x28-firewall-ui-backup-20261021}
test -f "$backup/firewall.lua"
test -f "$backup/vendor.lua"
old_leasefile=$(uci -c "$backup" -q get dhcp.@dnsmasq[0].leasefile)
test -n "$old_leasefile"
cp -p "$backup/firewall.lua" /usr/lib/lua/luci/controller/firewall.lua
cp -p "$backup/vendor.lua" /usr/lib/lua/luci/controller/vendor.lua
uci set "dhcp.@dnsmasq[0].leasefile=$old_leasefile"
uci commit dhcp
rm -f /tmp/luci-indexcache /tmp/luci-indexcache.*.json
rm -rf /tmp/luci-modulecache
printf 'Previous firewall navigation and lease-reader path restored. Log back into LuCI to refresh cached navigation.\n'
