#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# The user_data preinit hook against fakes: no device, flash or UBI involved.
set -e
dir=$(mktemp -d); trap 'rm -rf "$dir"' EXIT
export X28_UD_TEST=1 X28_UD_PROC="$dir/proc" X28_UD_SYS="$dir/sys" X28_UD_MNT="$dir/mnt"
mkdir -p "$dir/proc" "$dir/mnt/etc" "$dir/mnt/upper" "$dir/mnt/work" "$dir/mnt/log"
. "$(dirname "$0")/../package/x28-storage/files/x28-user-data.preinit"
attach_rc=0 mount_rc=0 uuid=NEW
ubiattach() { echo "attach $*" >> "$dir/calls"; return $attach_rc; }
mknod() { :; }
block() { echo "/dev/ubiblock0_0: UUID=\"$uuid\" VERSION=\"4.0\" TYPE=\"squashfs\""; }
mount() { echo mount >> "$dir/calls"; return $mount_rc; }
umount() { echo umount >> "$dir/calls"; }
reset() { : > "$dir/calls"; mkdir -p "$dir/mnt/upper" "$dir/mnt/work"; }
printf 'mtd49: 00400000 00040000 "productinfo"\nmtd50: 1ab80000 00040000 "user_data"\n' > "$dir/proc/mtd"

# Same image: the overlay stays.
reset; echo NEW > "$dir/mnt/etc/.extroot-uuid"; do_x28_user_data
grep -q '^attach /dev/ubi_ctrl -m 50 -d 1$' "$dir/calls" && [ -d "$dir/mnt/upper" ] && [ -f "$dir/mnt/etc/.extroot-uuid" ] || exit 1
# New image: the overlay and tag go, stock's files stay.
reset; echo OLD > "$dir/mnt/etc/.extroot-uuid"; do_x28_user_data
[ ! -e "$dir/mnt/upper" ] && [ ! -e "$dir/mnt/work" ] && [ ! -e "$dir/mnt/etc/.extroot-uuid" ] && [ -d "$dir/mnt/log" ] && grep -q umount "$dir/calls" || exit 1
# First boot: no tag yet, nothing is removed.
reset; rm -f "$dir/mnt/etc/.extroot-uuid"; do_x28_user_data
[ -d "$dir/mnt/upper" ] || exit 1
# Unknown root: nothing is removed.
reset; echo OLD > "$dir/mnt/etc/.extroot-uuid"; uuid=; do_x28_user_data; uuid=NEW
[ -d "$dir/mnt/upper" ] && ! grep -q mount "$dir/calls" || exit 1
# Volume does not mount: nothing is removed or unmounted.
reset; mount_rc=1; do_x28_user_data; mount_rc=0
[ -d "$dir/mnt/upper" ] && ! grep -q umount "$dir/calls" || exit 1
# Attach fails: stop there.
reset; attach_rc=1; do_x28_user_data; attach_rc=0
! grep -q mount "$dir/calls" || exit 1
# No user_data partition: no attach.
reset; echo 'mtd0: 00400000 00040000 "preloader"' > "$dir/proc/mtd"; do_x28_user_data
[ ! -s "$dir/calls" ] || exit 1
echo "PASS: user_data attach, new-image reset and every fall-back"
