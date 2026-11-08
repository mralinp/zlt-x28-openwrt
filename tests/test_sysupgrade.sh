#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# package/x28-sysupgrade against a file standing in for misc, a fake dd-nand and fake write/verify steps; no device involved.
set -e
dir=$(mktemp -d); trap 'rm -rf "$dir"' EXIT
mkdir -p "$dir/proc"
printf '%s\n' 'dev:    size   erasesize  name' 'mtd3: 00100000 00040000 "misc"' 'mtd28: 04000000 00040000 "rootfs_a"' 'mtd42: 04000000 00040000 "rootfs_b"' > "$dir/proc/mtd"
echo 'console=ttyS0 bootslot=a' > "$dir/proc/cmdline"
cat > "$dir/dd-nand" <<'STUB'
#!/bin/sh
echo x >> "$CALLS"
for a in "$@"; do case "$a" in of=*) f=${a#of=};; seek=*) s=${a#seek=};; count=*) c=${a#count=};; esac; done
[ -n "$FAILAT" ] && [ "$(wc -l < "$CALLS")" -ge "$FAILAT" ] && exit 1
dd of="$f" bs=1 seek="$s" count="$c" conv=notrunc 2>/dev/null
STUB
chmod +x "$dir/dd-nand"
CALLS=$dir/calls; export CALLS
mkmisc() { # $1 = A entry, $2 = B entry as hex (priority tries success up-type)
	dd if=/dev/zero bs=262144 count=4 2>/dev/null | tr '\0' '\377' > "$dir/misc"
	for i in 0 1 2 3; do
		printf '\000AB0\377\377\377\377' | dd of="$dir/misc" bs=1 seek=$((2048 + 262144 * i)) conv=notrunc 2>/dev/null
		printf "$(echo "$1$2" | sed 's/../\\x&/g')" | dd of="$dir/misc" bs=1 seek=$((2056 + 262144 * i)) conv=notrunc 2>/dev/null
	done
}
entries() { for i in 0 1 2 3; do dd if="$dir/misc" bs=1 skip=$((2056 + 262144 * i)) count=8 2>/dev/null | hexdump -v -e '1/1 "%02x"'; printf ' '; done; }
ALL() { printf '%s %s %s %s ' "$1" "$1" "$1" "$1"; }
mkdir -p "$dir/root/etc/init.d" "$dir/root/tmp" "$dir/dump"; : > "$dir/root/etc/init.d/x28-bootok"; chmod +x "$dir/root/etc/init.d/x28-bootok"
echo 'MemAvailable:     300000 kB' > "$dir/proc/meminfo"
export X28_UP_TEST=1 X28_UP_PROC=$dir/proc X28_UP_MISC=$dir/misc X28_UP_DDNAND=$dir/dd-nand X28_UP_ROOT=$dir/root X28_UP_TMP=$dir X28_UP_DUMP=$dir/dump X28_UP_SYS=$dir/sys X28_UP_DEVDIR=$dir/devx
. "$(dirname "$0")/../package/x28-sysupgrade/files/lib/upgrade/x28.sh"

# flip to B: B 15 tries 0, A 14, success and up-type bytes kept, in all four copies
mkmisc 0f000000 0e000101; : > "$CALLS"; x28_misc_select b 1 2>/dev/null
[ "$(entries)" = "$(ALL 0e0000000f000101)" ] && [ "$(wc -l < "$CALLS")" -eq 4 ]
# in place: only the running slot's tries go to 0; priorities untouched
mkmisc 0f050000 0e000101; x28_misc_select a 0 2>/dev/null; [ "$(entries)" = "$(ALL 0f0000000e000101)" ]
# copies are written last to first: a failure at the third call leaves copy 1 (the one read first) and copy 2 old, copies 4 and 3 new
mkmisc 0f000000 0e000101; : > "$CALLS"; ! (FAILAT=3; export FAILAT; x28_misc_select b 1) 2>/dev/null
[ "$(entries)" = "0f0000000e000101 0f0000000e000101 0e0000000f000101 0e0000000f000101 " ]
rc=0; mkmisc 0f000000 0e000101; (FAILAT=2; export FAILAT; x28_misc_select b 1) 2>/dev/null || rc=$?; [ "$rc" -eq 2 ]    # partial change is code 2
[ "$(ls "$dir/dump" | wc -l)" -ge 1 ] && [ "$(wc -c < "$dir/dump/$(ls "$dir/dump" | head -1)")" -eq 1048576 ]       # the dump is the whole partition
# a writer that damages a neighbouring byte is caught by the whole-partition compare, which the 8-byte read-back alone would miss
cat > "$dir/dd-nand4" <<'STUB'
#!/bin/sh
for a in "$@"; do case "$a" in of=*) f=${a#of=};; seek=*) s=${a#seek=};; count=*) c=${a#count=};; esac; done
dd of="$f" bs=1 seek="$s" count="$c" conv=notrunc 2>/dev/null
printf 'Z' | dd of="$f" bs=1 seek=$((s + 100)) count=1 conv=notrunc 2>/dev/null
STUB
chmod +x "$dir/dd-nand4"; mkmisc 0f000000 0e000101
rc=0; (X28_UP_DDNAND=$dir/dd-nand4; x28_misc_select b 1) 2>/dev/null || rc=$?; [ "$rc" -eq 2 ]
# a short write (fewer bytes than asked) is caught too
printf '#!/bin/sh\ntrue\n' > "$dir/dd-nand5"; chmod +x "$dir/dd-nand5"; mkmisc 0f000000 0e000101
rc=0; (X28_UP_DDNAND=$dir/dd-nand5; x28_misc_select b 1) 2>/dev/null || rc=$?; [ "$rc" -eq 2 ]
# bootslot=b flips to A the same way
echo 'bootslot=b' > "$dir/proc/cmdline"; mkmisc 0e000000 0f000101; x28_misc_select a 1 2>/dev/null; [ "$(entries)" = "$(ALL 0f0000000e000101)" ]; echo 'bootslot=a' > "$dir/proc/cmdline"
# mixed copies, a missing magic, no record: refused, nothing written
mkmisc 0f000000 0e000101; : > "$CALLS"; ! (FAILAT=3; export FAILAT; x28_misc_select b 1) 2>/dev/null   # mixed copies again
: > "$CALLS"; ! x28_misc_select b 1 2>/dev/null; [ ! -s "$CALLS" ]
mkmisc 0f000000 0e000101; printf 'X' | dd of="$dir/misc" bs=1 seek=$((2048 + 262144 * 2)) conv=notrunc 2>/dev/null
! x28_misc_select b 1 2>/dev/null; [ ! -s "$CALLS" ]
# the running slot must have no tries
mkmisc 0f050000 0e000101; ! x28_tries_zero "$dir/misc" 2>/dev/null
mkmisc 0f000000 0e000101; x28_tries_zero "$dir/misc" 2>/dev/null
echo 'bootslot=b' > "$dir/proc/cmdline"; mkmisc 0e000101 0f030000; ! x28_tries_zero "$dir/misc" 2>/dev/null
echo 'bootslot=a' > "$dir/proc/cmdline"
# target: in place without the marker, the other slot with it
[ "$(x28_target)" = "a 0" ]; : > "$dir/root/etc/x28-native-b"
! x28_target 2>/dev/null                                                              # marker alone is not enough
: > "$dir/root/tmp/x28-write-b-ok"; [ "$(x28_target)" = "b 1" ]
echo 'bootslot=b' > "$dir/proc/cmdline"; [ "$(x28_target)" = "a 1" ]; echo 'bootslot=a' > "$dir/proc/cmdline"; rm "$dir/root/etc/x28-native-b" "$dir/root/tmp/x28-write-b-ok"

# the tarball
mkdir -p "$dir/t/sysupgrade-x28"; head -c 4096 /dev/urandom > "$dir/t/sysupgrade-x28/root"
(cd "$dir/t/sysupgrade-x28" && sha256sum root | cut -d' ' -f1 > root.sha256 && head -c 1000 root | sha256sum | cut -d' ' -f1 | tr '\n' ' ' > root.rootfs && echo 1000 >> root.rootfs)
(cd "$dir/t" && tar -cf "$dir/good.tar" sysupgrade-x28)
mkmisc 0f000000 0e000101; platform_check_image "$dir/good.tar" 2>/dev/null
echo 0000 > "$dir/t/sysupgrade-x28/root.sha256"; (cd "$dir/t" && tar -cf "$dir/badhash.tar" sysupgrade-x28)
! platform_check_image "$dir/badhash.tar" 2>/dev/null
echo hello > "$dir/junk"; (cd "$dir" && tar -cf junk.tar junk); ! platform_check_image "$dir/junk.tar" 2>/dev/null
mkmisc 0f050000 0e000101; ! platform_check_image "$dir/good.tar" 2>/dev/null        # tries still counting

# the order: a failed write or verify leaves misc alone; success changes it only afterwards
: > "$dir/root/etc/x28-native-b"; : > "$dir/root/tmp/x28-write-b-ok"
X28_UP_WRITE=false X28_UP_VERIFY=true; mkmisc 0f000000 0e000101; : > "$CALLS"
! platform_do_upgrade "$dir/good.tar" 2>/dev/null; [ ! -s "$CALLS" ] && [ "$(entries)" = "$(ALL 0f0000000e000101)" ] && [ ! -e "$dir/x28-root.ubi" ]
X28_UP_WRITE=true X28_UP_VERIFY=false
! platform_do_upgrade "$dir/good.tar" 2>/dev/null; [ ! -s "$CALLS" ] && [ "$(entries)" = "$(ALL 0f0000000e000101)" ]
X28_UP_WRITE=true X28_UP_VERIFY=true
platform_do_upgrade "$dir/good.tar" 2>/dev/null; [ "$(entries)" = "$(ALL 0e0000000f000101)" ]
# the image is written to the right partition
X28_UP_WRITE='echo' ; mkmisc 0f000000 0e000101
[ "$(platform_do_upgrade "$dir/good.tar" 2>/dev/null)" = "$dir/x28-root.ubi /dev/mtd42" ]
# the check step: bootok missing, not enough RAM, image larger than the partition
mkmisc 0f000000 0e000101
chmod -x "$dir/root/etc/init.d/x28-bootok"; ! platform_check_image "$dir/good.tar" 2>/dev/null; chmod +x "$dir/root/etc/init.d/x28-bootok"
echo 'MemAvailable:      20000 kB' > "$dir/proc/meminfo"; ! platform_check_image "$dir/good.tar" 2>/dev/null
echo 'MemAvailable:     300000 kB' > "$dir/proc/meminfo"; platform_check_image "$dir/good.tar" 2>/dev/null
sed -i.bak 's/"rootfs_a"/"rootfs_a"/; s/^mtd28: 04000000/mtd28: 00000800/' "$dir/proc/mtd"; ! platform_check_image "$dir/good.tar" 2>/dev/null
sed -i.bak 's/^mtd28: 00000800/mtd28: 04000000/' "$dir/proc/mtd"
# the upgrade itself re-checks the running slot's tries
mkmisc 0f050000 0e000101; : > "$CALLS"; X28_UP_WRITE=true X28_UP_VERIFY=true; ! platform_do_upgrade "$dir/good.tar" 2>/dev/null; [ ! -s "$CALLS" ]
# the device steps with fake ubi-utils: detach only when attached, then ubiformat; the verify hashes the scratch volume
mkdir -p "$dir/sys/class/ubi/ubi0" "$dir/devx"; echo 28 > "$dir/sys/class/ubi/ubi0/mtd_num"; ULOG=$dir/ulog; : > "$ULOG"
ubiformat() { echo "ubiformat $*" >> "$ULOG"; }
ubidetach() { echo "ubidetach $*" >> "$ULOG"; }
ubiblock() { echo "ubiblock $*" >> "$ULOG"; }
ubiattach() { echo "ubiattach $*" >> "$ULOG"; head -c 1000 "$dir/t/sysupgrade-x28/root" > "$dir/devx/ubi9_0"; head -c 24 /dev/zero >> "$dir/devx/ubi9_0"; }
x28_ubi_write img /dev/mtd28 2>/dev/null
[ "$(cat "$ULOG")" = "$(printf 'ubiblock --remove %s/devx/ubi0_0\nubidetach -m 28\nubiformat /dev/mtd28 -y -f img' "$dir")" ]
: > "$ULOG"; x28_ubi_write img /dev/mtd42 2>/dev/null; [ "$(cat "$ULOG")" = "ubiformat /dev/mtd42 -y -f img" ]      # not attached: no detach
ubiformat() { return 1; }; ! x28_ubi_write img /dev/mtd42 2>/dev/null
X28_EXP_SHA=$(head -c 1000 "$dir/t/sysupgrade-x28/root" | sha256sum | cut -d' ' -f1) X28_EXP_BYTES=1000
: > "$ULOG"; x28_ubi_verify img /dev/mtd42 2>/dev/null; grep -q '^ubiattach /dev/ubi_ctrl -m 42 -d 9$' "$ULOG" && grep -q '^ubidetach -d 9$' "$ULOG"
X28_EXP_SHA=0000; ! x28_ubi_verify img /dev/mtd42 2>/dev/null; X28_EXP_SHA=; ! x28_ubi_verify img /dev/mtd42 2>/dev/null
unset -f ubiformat ubidetach ubiblock ubiattach
# without X28_UP_TEST the environment redirects nothing
[ "$(env -u X28_UP_TEST X28_UP_MISC=/tmp/evil X28_UP_PROC="$dir/proc" sh -c '. "$1"; echo "$X28_UP_MISC|$X28_UP_DDNAND"' x "$(dirname "$0")/../package/x28-sysupgrade/files/lib/upgrade/x28.sh")" = "|dd-nand" ]
echo "PASS: x28-sysupgrade checks first, writes and verifies the target, and changes misc only afterwards, copy 1 last"
