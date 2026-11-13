#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# The factory reset (firstboot) against a fake overlay, then the preinit hook's next boot on it: no device involved.
set -e
dir=$(mktemp -d); trap 'rm -rf "$dir"' EXIT
fb="$(dirname "$0")/../package/x28-storage/files/firstboot"
cat > "$dir/stub" <<'S'
#!/bin/sh
echo "$(basename "$0") $*" >> "$CALLS"
S
chmod +x "$dir/stub"; ln -s stub "$dir/reboot"; ln -s stub "$dir/jffs2reset"; ln -s stub "$dir/logger"; ln -s stub "$dir/sync"
export CALLS="$dir/calls" PATH="$dir:$PATH" X28_FB_OVERLAY="$dir/ov" X28_FB_REBOOT="$dir/reboot" X28_FB_JFFS2RESET="$dir/jffs2reset"
fresh() { rm -rf "$dir/ov"; mkdir -p "$dir/ov/etc" "$dir/ov/upper/etc" "$dir/ov/work" "$dir/ov/log"; echo UUID > "$dir/ov/etc/.extroot-uuid"; : > "$CALLS"; }

# LuCI's call: the tag is spoiled, kept settings go, the live upper is not touched, then reboot.
fresh; : > "$dir/ov/x28-keep-a.tgz"; sh "$fb" -r -y
[ "$(cat "$dir/ov/etc/.extroot-uuid")" = reset ] && [ ! -e "$dir/ov/x28-keep-a.tgz" ] && [ -d "$dir/ov/upper/etc" ] && grep -q '^reboot' "$CALLS" || exit 1
! grep -q jffs2reset "$CALLS" || exit 1
# -y alone marks and does not reboot; -yr together is understood.
fresh; sh "$fb" -y >/dev/null; [ "$(cat "$dir/ov/etc/.extroot-uuid")" = reset ] && ! grep -q '^reboot' "$CALLS" || exit 1
fresh; sh "$fb" -yr; grep -q '^reboot' "$CALLS" || exit 1
# No -y: asks; anything but y changes nothing.
fresh; ! echo n | sh "$fb" -r >/dev/null || exit 1
[ "$(cat "$dir/ov/etc/.extroot-uuid")" = UUID ] && ! grep -q '^reboot' "$CALLS" || exit 1
fresh; echo y | sh "$fb" >/dev/null; [ "$(cat "$dir/ov/etc/.extroot-uuid")" = reset ] || exit 1
# The overlay is not user_data (no tag): the stock reset runs with the same arguments.
fresh; rm "$dir/ov/etc/.extroot-uuid"; sh "$fb" -r -y
grep -q '^jffs2reset -r -y$' "$CALLS" && ! grep -q '^reboot' "$CALLS" && [ ! -e "$dir/ov/etc/.extroot-uuid" ] || exit 1

# The next boot: the preinit hook removes a marked overlay and keeps the other files on the volume.
fresh; sh "$fb" -y >/dev/null
export X28_UD_TEST=1 X28_UD_PROC="$dir/proc" X28_UD_SYS="$dir/sys" X28_UD_MNT="$dir/ov" X28_UD_DEV="$dir/dev"
mkdir -p "$dir/proc" "$dir/dev"
. "$(dirname "$0")/../package/x28-storage/files/x28-user-data.preinit"
ubiattach() { :; }; mknod() { :; }; mount() { :; }; umount() { :; }
block() { echo '/dev/ubiblock0_0: UUID="UUID" VERSION="4.0" TYPE="squashfs"'; }
printf 'mtd3: 00100000 00040000 "misc"\nmtd50: 1ab80000 00040000 "user_data"\n' > "$dir/proc/mtd"
echo 'console=x bootslot=a y' > "$dir/proc/cmdline"
head -c 2057 /dev/zero > "$dir/dev/mtd3"; printf '\001' >> "$dir/dev/mtd3"
do_x28_user_data
[ ! -e "$dir/ov/upper" ] && [ ! -e "$dir/ov/work" ] && [ ! -e "$dir/ov/etc/.extroot-uuid" ] && [ -d "$dir/ov/log" ] || exit 1
echo "PASS: firstboot marks the user_data overlay, the next boot removes it; without that overlay the stock reset runs"
