#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# The user_data preinit hook against fakes: no device, flash or UBI involved.
set -e
dir=$(mktemp -d); trap 'rm -rf "$dir"' EXIT
export X28_UD_TEST=1 X28_UD_PROC="$dir/proc" X28_UD_SYS="$dir/sys" X28_UD_MNT="$dir/mnt" X28_UD_DEV="$dir/dev"
mkdir -p "$dir/proc" "$dir/dev" "$dir/mnt/etc" "$dir/mnt/upper" "$dir/mnt/work" "$dir/mnt/log"
. "$(dirname "$0")/../package/x28-storage/files/x28-user-data.preinit"
attach_rc=0 mount_rc=0 uuid=NEW
ubiattach() { echo "attach $*" >> "$dir/calls"; return $attach_rc; }
mknod() { :; }
block() { echo "/dev/ubiblock0_0: UUID=\"$uuid\" VERSION=\"4.0\" TYPE=\"squashfs\""; }
mount() { echo mount >> "$dir/calls"; return $mount_rc; }
umount() { echo umount >> "$dir/calls"; }
reset() { : > "$dir/calls"; mkdir -p "$dir/mnt/upper" "$dir/mnt/work"; }
tries() { head -c 2057 /dev/zero > "$dir/dev/mtd3"; printf "\\00$1" >> "$dir/dev/mtd3"; }
printf 'mtd3: 00100000 00040000 "misc"\nmtd49: 00400000 00040000 "productinfo"\nmtd50: 1ab80000 00040000 "user_data"\n' > "$dir/proc/mtd"
echo 'console=x bootslot=a y' > "$dir/proc/cmdline"
tries 1

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
# A wipe that fails keeps the tag, so it repeats next boot.
reset; echo OLD > "$dir/mnt/etc/.extroot-uuid"; rm() { return 1; }; do_x28_user_data; unset -f rm
[ "$(cat "$dir/mnt/etc/.extroot-uuid")" = OLD ] || exit 1
# Tries 2 still attach; from 3 on user_data is left alone, also with an old tag.
reset; tries 2; do_x28_user_data; grep -q attach "$dir/calls" || exit 1
reset; tries 3; do_x28_user_data; [ ! -s "$dir/calls" ] && [ -d "$dir/mnt/upper" ] || exit 1
reset; tries 7; do_x28_user_data; [ ! -s "$dir/calls" ] || exit 1
# Slot B reads its own byte (2061), not A's: A at 7 does not stop B, B at 7 does.
echo 'bootslot=b' > "$dir/proc/cmdline"
reset; tries 7; do_x28_user_data; grep -q attach "$dir/calls" && echo "B: A's byte ignored" >/dev/null || exit 1
reset; { head -c 2061 /dev/zero; printf '\007'; } > "$dir/dev/mtd3"; do_x28_user_data; [ ! -s "$dir/calls" ] || exit 1
echo 'bootslot=a' > "$dir/proc/cmdline"
# misc unreadable: go on.
reset; /bin/rm -f "$dir/dev/mtd3"; do_x28_user_data; grep -q attach "$dir/calls" || exit 1
# No user_data partition: no attach.
reset; echo 'mtd0: 00400000 00040000 "preloader"' > "$dir/proc/mtd"; do_x28_user_data
[ ! -s "$dir/calls" ] || exit 1
# Kept settings (#477): only a new image on the slot they were saved for restores them, without anything that runs at boot.
printf 'mtd3: 00100000 00040000 "misc"\nmtd50: 1ab80000 00040000 "user_data"\n' > "$dir/proc/mtd"; tries 0
mkdir -p "$dir/src/etc/config" "$dir/src/etc/init.d" "$dir/src/etc/crontabs" "$dir/src/usr/bin"
echo net > "$dir/src/etc/config/network"; echo x > "$dir/src/etc/init.d/evil"; echo x > "$dir/src/etc/rc.local"
echo x > "$dir/src/etc/crontabs/root"; echo x > "$dir/src/usr/bin/evil"; echo x > "$dir/src/etc/sysctl.conf"
mkdir -p "$dir/src/etc/dropbear"; echo k > "$dir/src/etc/dropbear/authorized_keys"
(cd "$dir/src" && tar -czf "$dir/keep.tgz" etc usr)
kept() { tar -tzf "$dir/mnt/upper/sysupgrade.tgz" | sed 's|^\./||' | grep -v '/$' | sort | tr '\n' ' '; }
reset; echo OLD > "$dir/mnt/etc/.extroot-uuid"; cp "$dir/keep.tgz" "$dir/mnt/x28-keep-a.tgz"; cp "$dir/keep.tgz" "$dir/mnt/x28-keep-b.tgz"
do_x28_user_data >/dev/null
[ "$(kept)" = "etc/config/network etc/dropbear/authorized_keys " ] && [ ! -e "$dir/mnt/x28-keep-a.tgz" ] && [ ! -e "$dir/mnt/x28-keep-b.tgz" ] || { kept; exit 1; }
# Same image (e.g. back on the old slot): the backup is dropped, the overlay untouched.
/bin/rm -rf "$dir/mnt/upper"; reset; echo NEW > "$dir/mnt/etc/.extroot-uuid"; cp "$dir/keep.tgz" "$dir/mnt/x28-keep-a.tgz"; do_x28_user_data >/dev/null
[ ! -e "$dir/mnt/upper/sysupgrade.tgz" ] && [ ! -e "$dir/mnt/x28-keep-a.tgz" ] || exit 1
# Saved for the other slot, or an archive with ../ or unreadable: nothing restored.
for bad in b dotdot junk link; do
	/bin/rm -rf "$dir/mnt/upper"; reset; echo OLD > "$dir/mnt/etc/.extroot-uuid"
	case $bad in
		b) cp "$dir/keep.tgz" "$dir/mnt/x28-keep-b.tgz" ;;
		dotdot) (cd "$dir/src/etc" && tar -P -czf "$dir/mnt/x28-keep-a.tgz" ../etc/config/network) ;;  # -P: GNU tar strips ../ otherwise
		junk) echo junk > "$dir/mnt/x28-keep-a.tgz" ;;
		link) mkdir -p "$dir/l/etc"; ln -s /nonexistent "$dir/l/etc/inittab"; echo n > "$dir/l/etc/passwd"; (cd "$dir/l" && tar -czf "$dir/mnt/x28-keep-a.tgz" etc) ;;
	esac
	do_x28_user_data >/dev/null; [ ! -e "$dir/mnt/upper/sysupgrade.tgz" ] && [ -z "$(ls "$dir/mnt" | grep keep)" ] || { echo "case $bad"; exit 1; }
done
# First use of the volume (no tag yet) takes them too.
/bin/rm -rf "$dir/mnt/upper"; reset; /bin/rm -f "$dir/mnt/etc/.extroot-uuid"; cp "$dir/keep.tgz" "$dir/mnt/x28-keep-a.tgz"; do_x28_user_data >/dev/null
[ "$(kept)" = "etc/config/network etc/dropbear/authorized_keys " ] || exit 1
echo "PASS: user_data attach, new-image reset, boot-tries bypass and every fall-back; kept settings restored only for a new image, settings and keys only"
