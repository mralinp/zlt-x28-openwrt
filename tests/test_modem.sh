#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Partition name links of the x28-modem boot script against a fake /proc; no device, mount or daemon involved.
set -e
dir=$(mktemp -d); trap 'rm -rf "$dir"' EXIT
mkdir -p "$dir/proc" "$dir/dev"
printf '%s\n' 'dev:    size   erasesize  name' 'mtd3: 00100000 00040000 "misc"' 'mtd27: 00800000 00040000 "boot_a"' \
	'mtd40: 00800000 00040000 "boot_b"' 'mtd29: 05000000 00040000 "rootfs_a"' > "$dir/proc/mtd"
echo 'console=ttyS0 root=/dev/ubiblock0_0 bootslot=a  androidboot.hardware=mt6890' > "$dir/proc/cmdline"
X28_MODEM_PROC=$dir/proc X28_MODEM_DEV=$dir/dev . "$(dirname "$0")/../package/x28-modem/files/x28-modem.init"
log() { echo "$*" >&2; }
links
[ "$(readlink "$dir/dev/mtd/misc")" = /dev/mtd3 ] && [ "$(readlink "$dir/dev/block/boot_a")" = /dev/mtdblock27 ]
[ "$(readlink "$dir/dev/block/boot")" = /dev/block/boot_a ] && [ "$(readlink "$dir/dev/mtd/rootfs")" = /dev/mtd/rootfs_a ]
links  # idempotent
[ "$(readlink "$dir/dev/block/boot")" = /dev/block/boot_a ]
echo 'console=ttyS0' > "$dir/proc/cmdline"
! links 2>/dev/null
# Wi-Fi: no radio, nothing to do; radio and no config: create it, then reload; config present: only reload.
calls=$dir/calls; wifi() { echo "$*" >> "$calls"; }
SYS=$dir/sys; CFG=$dir/cfg; mkdir -p "$CFG" "$SYS/class/net"; : > "$calls"
wireless; [ ! -s "$calls" ]
mkdir "$SYS/class/net/ra0"; wireless; [ "$(tr '\n' ' ' < "$calls")" = "config reload " ]
: > "$calls"; : > "$CFG/wireless"; wireless; [ "$(tr '\n' ' ' < "$calls")" = "reload " ]
echo "PASS: x28-modem partition name links, active-slot aliases and Wi-Fi bring-up"
