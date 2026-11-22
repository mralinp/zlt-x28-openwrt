#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# netifd's switch hook (/etc/init.d/network includes /lib/network and calls setup_switch on start and reload), so
# Network > Switch in LuCI reprograms the MT7531AE on Save & Apply. Not the vendor initializer: no PHY/GPIO writes.
# Guard before `load` (it applies at once): the chip must be the known one, and the table must keep one VLAN with a
# tagged CPU port and one untagged LAN port, or the new table is refused and the running one stays.

x28_switch_ok() {
	local cpu lan p
	for p in $(uci -q show network | sed -n "s/^network\.@switch_vlan\[[0-9]*\]\.ports='\(.*\)'$/\1/p"); do
		case $p in *t) cpu=1 ;; *) lan=1 ;; esac
	done
	[ -n "$cpu" ] && [ -n "$lan" ]
}

setup_switch() {
	rm -f /tmp/x28-switch.failed
	[ "$(swconfig list 2>/dev/null)" = "Found: switch0 - MT7531AE" ] || { echo "x28-switch: unexpected switch" >&2; : > /tmp/x28-switch.failed; return 1; }
	x28_switch_ok || { echo "x28-switch: table has no tagged CPU port or no untagged LAN port, not applied" >&2; : > /tmp/x28-switch.failed; return 1; }
	swconfig dev switch0 load network || { echo "x28-switch: load failed" >&2; : > /tmp/x28-switch.failed; return 1; }
}
