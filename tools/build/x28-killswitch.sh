#!/bin/sh
# ICMP stays direct: Xray cannot proxy it, and blocking errors breaks path MTU discovery.
set -e
enabled="$(uci -q get passwall2.@global[0].enabled || :)"
for family in iptables ip6tables; do
	protocol=icmp
	[ "$family" != ip6tables ] || protocol=ipv6-icmp
	if ! "$family" -nL x28_killswitch >/dev/null 2>&1; then
		"$family" -N x28_killswitch
	fi
	if [ "$enabled" = 1 ]; then
		if ! "$family" -C x28_killswitch -o ccmni+ ! -p "$protocol" -j REJECT >/dev/null 2>&1; then
			"$family" -A x28_killswitch -o ccmni+ ! -p "$protocol" -j REJECT
		fi
	else
		"$family" -F x28_killswitch
	fi
	if ! "$family" -C forwarding_rule -j x28_killswitch >/dev/null 2>&1; then
		"$family" -I forwarding_rule -j x28_killswitch
	fi
done
