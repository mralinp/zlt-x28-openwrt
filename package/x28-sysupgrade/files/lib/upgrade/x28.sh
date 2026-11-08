# SPDX-License-Identifier: GPL-2.0-only
# Platform hooks and the misc writer for sysupgrade on the X28 A/B layout (#457, design: docs/research/sysupgrade-design.md).
# NOT in any image yet: the build guard refuses these tools until the reviewed exception exists (x28-flasher#81).
#
# Order is the point: check, write the target from RAM, verify it, and only then touch misc (priority flip and tries 0).
# The record is 0x20 bytes at 2048 in each of four copies 262144 apart: magic, ff*4, then per slot priority, tries, success, up-type
# (A at +8, B at +12). The preloader reads the first copy whose magic matches, so copies are written last to first.
# Tests (tests/test_sysupgrade.sh) point these at fakes.

# The environment can redirect nothing in production: these are fixed unless X28_UP_TEST is set (tests/test_sysupgrade.sh).
if [ -z "$X28_UP_TEST" ]; then
	X28_UP_PROC=/proc X28_UP_DDNAND=dd-nand X28_UP_MISC= X28_UP_ROOT= X28_UP_TMP=/tmp X28_UP_DUMP=/root
	X28_UP_WRITE=x28_ubi_write X28_UP_VERIFY=x28_ubi_verify
fi
X28_UP_PROC=${X28_UP_PROC:-/proc}
X28_UP_DDNAND=${X28_UP_DDNAND:-dd-nand}
X28_UP_MISC=${X28_UP_MISC:-}		# misc device; found in /proc/mtd when empty
X28_UP_ROOT=${X28_UP_ROOT:-}		# prefix of /etc for the marker, the confirmation file and the bootok check
X28_UP_TMP=${X28_UP_TMP:-/tmp}
X28_UP_DUMP=${X28_UP_DUMP:-/root}	# persistent: the overlay is on user_data
X28_COPY=262144
X28_DIR=sysupgrade-x28
X28_MIN_FREE_KB=32768

# The device steps are not written yet (design: the verify attaches the result and compares the volumes). Until then: fail closed.
x28_ubi_write() { x28_log "ubiformat step not implemented"; return 1; }
x28_ubi_verify() { x28_log "volume verify not implemented"; return 1; }

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
# First the whole partition is dumped to persistent storage (size and non-empty checked). One dd-nand call per copy rewrites all eight
# entry bytes, so no copy ever holds two equal priorities. After each copy the WHOLE partition is compared with the dump plus the copies
# written so far. A failure stops at once; copies 4 and 3 may be new while 2 and 1 are old, which the preloader reads as the old state.
x28_misc_select() {
	local target=$1 flip=$2 dev e a b i v out ap bp dump exp
	dev=$(x28_misc_dev) || { x28_log "no single misc partition"; return 1; }
	e=$(x28_misc_entries "$dev") || return 1
	dump=$X28_UP_DUMP/misc-$(date +%Y%m%d-%H%M%S).bin; exp=$X28_UP_TMP/misc-expected.bin
	dd if="$dev" of="$dump" bs=65536 2>/dev/null
	[ "$(wc -c < "$dump")" -eq 1048576 ] && dd if="$dev" bs=65536 2>/dev/null | cmp -s - "$dump" || { x28_log "misc dump failed; nothing written"; return 1; }
	cp "$dump" "$exp" || { x28_log "cannot stage the comparison copy; nothing written"; return 1; }
	a=$(echo "$e" | cut -c1-8); b=$(echo "$e" | cut -c9-16)
	if [ "$flip" = 1 ]; then
		ap=0e; bp=0e
		if [ "$target" = a ]; then ap=0f; else bp=0f; fi
		a=$ap$(echo "$a" | cut -c3-8); b=$bp$(echo "$b" | cut -c3-8)
	fi
	if [ "$target" = a ]; then a=$(echo "$a" | cut -c1-2)00$(echo "$a" | cut -c5-8)
	else b=$(echo "$b" | cut -c1-2)00$(echo "$b" | cut -c5-8); fi
	e=$a$b
	out=
	for v in 1 3 5 7 9 11 13 15; do out="$out\\$(printf %03o "0x$(echo "$e" | cut -c$v-$((v + 1)))")"; done
	for i in 3 2 1 0; do
		printf "$out" | "$X28_UP_DDNAND" of="$dev" seek=$((2056 + X28_COPY * i)) bs=1 count=8 >/dev/null 2>&1
		printf "$out" | dd of="$exp" bs=1 seek=$((2056 + X28_COPY * i)) count=8 conv=notrunc 2>/dev/null
		dd if="$dev" bs=65536 2>/dev/null | cmp -s - "$exp" || { x28_log "copy $((i + 1)): the partition differs from what was expected; stopped. Dump: $dump"; rm -f "$exp"; return 2; }
	done
	rm -f "$exp"
}

# The slot that gets the image: the running slot (in place) unless B is native. Native B needs the image's marker AND the operator's
# confirmation file, so a marker carried in A's image alone can never make sysupgrade overwrite a stock B.
x28_target() {
	local s; s=$(x28_slot)
	if [ ! -e "$X28_UP_ROOT/etc/x28-native-b" ]; then echo "$s 0"; return 0; fi
	if [ ! -e "$X28_UP_ROOT/tmp/x28-write-b-ok" ]; then x28_log "slot B is marked native: create /tmp/x28-write-b-ok to confirm writing it"; return 1; fi
	if [ "$s" = a ]; then echo "b 1"; else echo "a 1"; fi
}

x28_mtd_of() { sed -n "s/^\\(mtd[0-9]*\\): [0-9a-f]* [0-9a-f]* \"$1\"\$/\\1/p" "$X28_UP_PROC/mtd"; }

x28_mtd_of_size() { printf '%d' "0x$(sed -n "s/^mtd[0-9]*: \\([0-9a-f]*\\) [0-9a-f]* \"$1\"\$/\\1/p" "$X28_UP_PROC/mtd")"; }

x28_free_kb() { sed -n 's/^MemAvailable: *\([0-9]*\) kB.*/\1/p' "$X28_UP_PROC/meminfo"; }

# $1 = sysupgrade tarball: sysupgrade-x28/root (the UBI image) and sysupgrade-x28/root.sha256 (its hash).
platform_check_image() {
	local f=$1 want got dev size t flip free
	tar -tf "$f" 2>/dev/null | grep -qx "$X28_DIR/root" && tar -tf "$f" | grep -qx "$X28_DIR/root.sha256" || { x28_log "not an X28 sysupgrade file"; return 1; }
	want=$(tar -xOf "$f" "$X28_DIR/root.sha256") && got=$(tar -xOf "$f" "$X28_DIR/root" | sha256sum | cut -d' ' -f1)
	[ -n "$want" ] && [ "${want%% *}" = "$got" ] || { x28_log "image hash does not match"; return 1; }
	[ -x "$X28_UP_ROOT/etc/init.d/x28-bootok" ] || { x28_log "x28-bootok is not installed"; return 1; }
	dev=$(x28_misc_dev) || { x28_log "no single misc partition"; return 1; }
	x28_tries_zero "$dev" || return 1
	set -- $(x28_target) || return 1; t=$1
	size=$(tar -xOf "$f" "$X28_DIR/root" | wc -c)
	[ "$size" -gt 0 ] && [ "$size" -le "$(x28_mtd_of_size "rootfs_$t")" ] || { x28_log "image does not fit rootfs_$t"; return 1; }
	free=$(x28_free_kb)
	[ -n "$free" ] && [ "$free" -gt $((size / 1024 + X28_MIN_FREE_KB)) ] || { x28_log "not enough free RAM to hold the image"; return 1; }
}

# X28_UP_WRITE IMAGE MTD and X28_UP_VERIFY IMAGE MTD are the device steps (ubiformat from RAM; attach and compare the volumes).
# ponytail: ubiformat rewrites erase counters, so a byte compare of the whole mtd cannot be the check; the verify must read the volumes.
# Returns 2 when misc was partly changed: the caller must NOT reboot into the target then (the old slot still boots; see the dump).
platform_do_upgrade() {
	local f=$1 t flip mtd want img=$X28_UP_TMP/x28-root.ubi
	x28_tries_zero "$(x28_misc_dev)" || return 1
	set -- $(x28_target) || return 1; t=$1; flip=$2
	mtd=$(x28_mtd_of "rootfs_$t"); [ -n "$mtd" ] || { x28_log "no rootfs_$t"; return 1; }
	x28_misc_entries "$(x28_misc_dev)" >/dev/null || return 1
	want=$(tar -xOf "$f" "$X28_DIR/root.sha256") && want=${want%% *}
	if ! tar -xOf "$f" "$X28_DIR/root" > "$img" || [ "$(sha256sum < "$img" | cut -d' ' -f1)" != "$want" ]; then rm -f "$img"; x28_log "cannot unpack the image to RAM; nothing written"; return 1; fi
	$X28_UP_WRITE "$img" "/dev/$mtd" && $X28_UP_VERIFY "$img" "/dev/$mtd" || { rm -f "$img"; x28_log "write or verify failed; misc untouched"; return 1; }
	rm -f "$img"
	x28_misc_select "$t" "$flip"
}
