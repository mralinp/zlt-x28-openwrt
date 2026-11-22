#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# netifd's switch hook (/etc/init.d/network includes /lib/network and calls setup_switch on start and reload), so
# Network > Switch in LuCI reprograms the MT7531AE on Save & Apply. Not the vendor initializer: no PHY/GPIO writes.
# `load` applies at once and resets the switch (LAN links blink), so before it: the chip must be the known one and
# every VLAN that holds a LAN socket (0,1,2,4) must also carry a tagged CPU port (5t/6t), with at least one such VLAN.
# After it, each VLAN's ports are read back. A refusal leaves the running table; a failed load may not.

x28_sw_fail() { echo "x28-switch: $*" >&2; : > /tmp/x28-switch.failed; return 1; }

x28_switch_ok() {
	local s p ports cpu lan any
	for s in $(uci -q show network | sed -n 's/^network\.\([^.=]*\)=switch_vlan$/\1/p'); do
		ports=$(uci -q get network.$s.ports); cpu=; lan=
		for p in $ports; do
			case $p in 5t|6t) cpu=1 ;; 0|1|2|4) lan=1 ;; esac
		done
		[ -n "$lan" ] && { [ -n "$cpu" ] || return 1; any=1; }
	done
	[ -n "$any" ]
}

x28_switch_verify() {
	local s v want got
	for s in $(uci -q show network | sed -n 's/^network\.\([^.=]*\)=switch_vlan$/\1/p'); do
		v=$(uci -q get network.$s.vlan)
		want=$(for p in $(uci -q get network.$s.ports); do echo $p; done | sort | tr '\n' ' ')
		got=$(for p in $(swconfig dev switch0 vlan $v get ports 2>/dev/null); do echo $p; done | sort | tr '\n' ' ')
		[ "$want" = "$got" ] || return 1
	done
}

setup_switch() {
	rm -f /tmp/x28-switch.failed
	[ "$(swconfig list 2>/dev/null)" = "Found: switch0 - MT7531AE" ] || { x28_sw_fail "unexpected switch"; return 1; }
	x28_switch_ok || { x28_sw_fail "a VLAN with a LAN socket lacks a tagged CPU port (5t/6t), or there is none; not applied"; return 1; }
	swconfig dev switch0 load network || { x28_sw_fail "load failed"; return 1; }
	x28_switch_verify || { x28_sw_fail "read-back differs from /etc/config/network"; return 1; }
}
