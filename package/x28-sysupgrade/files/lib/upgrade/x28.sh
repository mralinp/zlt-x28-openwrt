# SPDX-License-Identifier: GPL-2.0-only
# Platform hooks and the misc writer for sysupgrade on the X28 A/B layout (#457, design: docs/research/sysupgrade-design.md).
# NOT in any image yet: the build guard refuses these tools until the reviewed exception exists (x28-flasher#81).
#
# Order is the point: check, write the target from RAM, verify it, and only then touch misc (priority flip and tries 0).
# The record is 0x20 bytes at 2048 in each of four copies 262144 apart: magic, ff*4, then per slot priority, tries, success, up-type
# (A at +8, B at +12). The preloader reads the first copy whose magic matches, so copies are written last to first.
# Tests (tests/test_sysupgrade.sh) point these at fakes.

X28_UP_PROC=${X28_UP_PROC:-/proc}
X28_UP_DDNAND=${X28_UP_DDNAND:-dd-nand}
X28_UP_MISC=${X28_UP_MISC:-}		# misc device; found in /proc/mtd when empty
X28_UP_MARK=${X28_UP_MARK:-/etc/x28-native-b}	# present when slot B carries a native image (image build writes it)
X28_COPY=262144
X28_DIR=sysupgrade-x28

x28_log() { echo "x28-sysupgrade: $*" >&2; }

x28_slot() { sed -n 's/.*bootslot=\([ab]\).*/\1/p' "$X28_UP_PROC/cmdline"; }

x28_hex() { dd if="$1" bs=1 skip=$(($2)) count=$(($3)) 2>/dev/null | hexdump -v -e '1/1 "%02x"'; }

x28_misc_dev() {
	if [ -n "$X28_UP_MISC" ]; then echo "$X28_UP_MISC"; return 0; fi
	local n
	n=$(sed -n 's/^\(mtd[0-9]*\): [0-9a-f]* [0-9a-f]* "misc"$/\1/p' "$X28_UP_PROC/mtd")
	case "$n" in mtd[0-9]*) [ "$(echo "$n" | wc -l)" -eq 1 ] || return 1; echo "/dev/$n" ;; *) return 1 ;; esac
}

# Every copy has the magic and the same slot entries; prints the 16 hex digits of the entries (A then B).
x28_misc_entries() {
	local dev=$1 i first cur
	for i in 0 1 2 3; do
		[ "$(x28_hex "$dev" $((2048 + X28_COPY * i)) 4)" = 00414230 ] || { x28_log "copy $((i + 1)): no boot-control record"; return 1; }
		cur=$(x28_hex "$dev" $((2056 + X28_COPY * i)) 8)
		if [ -n "$first" ] && [ "$cur" != "$first" ]; then x28_log "copies differ; refusing"; return 1; fi
		first=$cur
	done
	echo "$first"
}

# The running slot's tries must be 0: a slot that is still counting is not a base to upgrade from.
x28_tries_zero() {
	local e off
	e=$(x28_misc_entries "$1") || return 1
	case "$(x28_slot)" in a) off=2 ;; b) off=10 ;; *) x28_log "no bootslot"; return 1 ;; esac
	[ "$(echo "$e" | cut -c$((off + 1))-$((off + 2)))" = 00 ] || { x28_log "running slot still has boot tries; reboot first"; return 1; }
}

# x28_misc_select TARGET FLIP: TARGET (a|b) tries -> 0; FLIP=1 also gives it priority 15 and the other slot 14.
# One dd-nand call per copy rewrites all eight entry bytes, so no copy ever holds two equal priorities. Each copy is read back.
x28_misc_select() {
	local target=$1 flip=$2 dev e a b i v out ap bp
	dev=$(x28_misc_dev) || { x28_log "no single misc partition"; return 1; }
	e=$(x28_misc_entries "$dev") || return 1
	a=$(echo "$e" | cut -c1-8); b=$(echo "$e" | cut -c9-16)
	if [ "$flip" = 1 ]; then
		ap=0e; bp=0e
		if [ "$target" = a ]; then ap=0f; else bp=0f; fi
		a=$ap$(echo "$a" | cut -c3-8); b=$bp$(echo "$b" | cut -c3-8)
	fi
	if [ "$target" = a ]; then a=$(echo "$a" | cut -c1-2)00$(echo "$a" | cut -c5-8)
	else b=$(echo "$b" | cut -c1-2)00$(echo "$b" | cut -c5-8); fi
	e=$a$b
	for i in 3 2 1 0; do
		out=
		for v in 1 3 5 7 9 11 13 15; do out="$out\\$(printf %03o "0x$(echo "$e" | cut -c$v-$((v + 1)))")"; done
		printf "$out" | "$X28_UP_DDNAND" of="$dev" seek=$((2056 + X28_COPY * i)) bs=1 count=8 >/dev/null 2>&1
		[ "$(x28_hex "$dev" $((2056 + X28_COPY * i)) 8)" = "$e" ] || { x28_log "copy $((i + 1)): read-back differs; stopped"; return 1; }
	done
}

# The slot that gets the image: the other one when B is native, otherwise the running slot (written in place).
x28_target() {
	local s; s=$(x28_slot)
	if [ ! -e "$X28_UP_MARK" ]; then echo "$s 0"; elif [ "$s" = a ]; then echo "b 1"; else echo "a 1"; fi
}

x28_mtd_of() { sed -n "s/^\\(mtd[0-9]*\\): [0-9a-f]* [0-9a-f]* \"$1\"\$/\\1/p" "$X28_UP_PROC/mtd"; }

# $1 = sysupgrade tarball: sysupgrade-x28/root (the UBI image) and sysupgrade-x28/root.sha256 (its hash).
platform_check_image() {
	local f=$1 want got dev
	tar -tf "$f" 2>/dev/null | grep -qx "$X28_DIR/root" && tar -tf "$f" | grep -qx "$X28_DIR/root.sha256" || { x28_log "not an X28 sysupgrade file"; return 1; }
	want=$(tar -xOf "$f" "$X28_DIR/root.sha256") && got=$(tar -xOf "$f" "$X28_DIR/root" | sha256sum | cut -d' ' -f1)
	[ -n "$want" ] && [ "${want%% *}" = "$got" ] || { x28_log "image hash does not match"; return 1; }
	dev=$(x28_misc_dev) || { x28_log "no single misc partition"; return 1; }
	x28_tries_zero "$dev"
}

# X28_UP_WRITE IMAGE MTD and X28_UP_VERIFY IMAGE MTD are the device steps (ubiformat from RAM; compare the volumes after attaching).
# ponytail: ubiformat rewrites erase counters, so a byte compare of the whole mtd cannot be the check; the verify must read the volumes.
platform_do_upgrade() {
	local f=$1 t flip mtd img=${X28_UP_TMP:-/tmp}/x28-root.ubi
	set -- $(x28_target); t=$1; flip=$2
	mtd=$(x28_mtd_of "rootfs_$t"); [ -n "$mtd" ] || { x28_log "no rootfs_$t"; return 1; }
	x28_misc_entries "$(x28_misc_dev)" >/dev/null || return 1
	tar -xOf "$f" "$X28_DIR/root" > "$img" || { x28_log "cannot unpack to RAM"; return 1; }
	$X28_UP_WRITE "$img" "/dev/$mtd" && $X28_UP_VERIFY "$img" "/dev/$mtd" || { rm -f "$img"; x28_log "write or verify failed; misc untouched"; return 1; }
	rm -f "$img"
	x28_misc_select "$t" "$flip"
}
