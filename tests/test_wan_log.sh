#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# The iface hook of x28-wanlog (#667): logs wan/wan6 up and down only, and never ends the sourcing hotplug-call.
H=$(dirname "$0")/../package/x28-mipc/files/x28-wanlog.hotplug
fail() { echo "FAIL: $*"; exit 1; }
out=
logger() { out="$out|$*"; }
ev() { INTERFACE=$1 ACTION=$2 DEVICE=$3; . "$H"; }
ev wan ifdown ccmni1; ev wan ifup ccmni2; ev wan6 ifup ''; ev lan ifup br-lan; ev wan ifupdate ccmni2; ev wan ifup-failed ''
[ "$out" = "|-t x28-wan wan ifdown on ccmni1|-t x28-wan wan ifup on ccmni2|-t x28-wan wan6 ifup|-t x28-wan wan ifup-failed" ] ||
	fail "logged: $out"
echo 'PASS: wan/wan6 up and down are logged, other events are not, and the hook returns to hotplug-call'
