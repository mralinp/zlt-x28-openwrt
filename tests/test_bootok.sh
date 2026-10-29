#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# x28-bootok against a file standing in for misc and a fake dd-nand; no device, flash or vendor binary involved.
set -e
dir=$(mktemp -d); trap 'rm -rf "$dir"' EXIT
mkdir -p "$dir/proc"
printf '%s\n' 'dev:    size   erasesize  name' 'mtd3: 00100000 00040000 "misc"' > "$dir/proc/mtd"
echo 'console=ttyS0 bootslot=a androidboot.hardware=mt6890' > "$dir/proc/cmdline"
# fake dd-nand: the stock call, `dd-nand of=F seek=N bs=1 count=1` with the byte on stdin
cat > "$dir/dd-nand" <<'STUB'
#!/bin/sh
echo x >> "$CALLS"
for a in "$@"; do case "$a" in of=*) f=${a#of=};; seek=*) s=${a#seek=};; esac; done
[ -n "$FAIL" ] && exit 1
dd of="$f" bs=1 seek="$s" count=1 conv=notrunc 2>/dev/null
STUB
chmod +x "$dir/dd-nand"
CALLS=$dir/calls; export CALLS
mkmisc() { # four copies of an A record with the given tries byte (octal, e.g. 005), like the real partition
	dd if=/dev/zero bs=262144 count=4 2>/dev/null | tr '\0' '\377' > "$dir/misc"
	for i in 0 1 2 3; do
		printf "\\000AB0\\377\\377\\377\\377\\017\\$1\\000\\000\\016\\000\\001\\000" | dd of="$dir/misc" bs=1 seek=$((2048 + 262144 * i)) conv=notrunc 2>/dev/null
	done
}
tries() { for i in 0 1 2 3; do dd if="$dir/misc" bs=1 skip=$((2057 + 262144 * i)) count=1 2>/dev/null | hexdump -v -e '1/1 "%02x"'; printf ' '; done; }
logger() { :; }
X28_BOOTOK_PROC=$dir/proc X28_BOOTOK_DEV=$dir/misc X28_BOOTOK_DDNAND=$dir/dd-nand . "$(dirname "$0")/../package/x28-bootok/files/x28-bootok.init"

mkmisc 005; : > "$CALLS"; reset_tries 2>/dev/null
[ "$(tries)" = "00 00 00 00 " ] && [ "$(wc -l < "$CALLS")" -eq 4 ]            # all four reset
: > "$CALLS"; reset_tries 2>/dev/null; [ ! -s "$CALLS" ]                         # already 0: nothing written
mkmisc 005; dd if=/dev/zero of="$dir/misc" bs=1 seek=$((2048 + 262144 * 2 + 1)) count=1 conv=notrunc 2>/dev/null
: > "$CALLS"; ! reset_tries 2>/dev/null; [ ! -s "$CALLS" ]                       # not a boot-control record: nothing written
mkmisc 005; echo 'console=ttyS0 bootslot=b' > "$dir/proc/cmdline"
: > "$CALLS"; reset_tries 2>/dev/null; [ ! -s "$CALLS" ] && [ "$(tries)" = "05 05 05 05 " ]   # slot B: never written
echo 'console=ttyS0 bootslot=a' > "$dir/proc/cmdline"; mkmisc 005; : > "$CALLS"
! FAIL=1 reset_tries 2>/dev/null; [ "$(wc -l < "$CALLS")" -eq 1 ]               # a failed write stops after the first copy
[ "$(tries)" = "05 05 05 05 " ]
# a failure on the third write stops there: copies 4 and 3 stay reset, copies 2 and 1 are left alone
cat > "$dir/dd-nand2" <<'STUB'
#!/bin/sh
echo x >> "$CALLS"
for a in "$@"; do case "$a" in of=*) f=${a#of=};; seek=*) s=${a#seek=};; esac; done
[ "$(wc -l < "$CALLS")" -ge 3 ] && exit 1
dd of="$f" bs=1 seek="$s" count=1 conv=notrunc 2>/dev/null
STUB
chmod +x "$dir/dd-nand2"; mkmisc 005; : > "$CALLS"
! DDNAND=$dir/dd-nand2 reset_tries 2>/dev/null; [ "$(tries)" = "05 05 00 00 " ]
# a writer that exits 0 without writing is caught by the read-back
printf '#!/bin/sh\ntrue\n' > "$dir/dd-nand3"; chmod +x "$dir/dd-nand3"; mkmisc 005
! DDNAND=$dir/dd-nand3 reset_tries 2>/dev/null; [ "$(tries)" = "05 05 05 05 " ]
# no misc partition, or two of them, with no device given: nothing is written
DEV_SAVE=$DEV; DEV=; : > "$CALLS"
printf '%s\n' 'mtd3: 00100000 00040000 "boot_para"' > "$dir/proc/mtd"; ! reset_tries 2>/dev/null
printf '%s\n' 'mtd3: 00100000 00040000 "misc"' 'mtd9: 00100000 00040000 "misc"' > "$dir/proc/mtd"; ! reset_tries 2>/dev/null
[ ! -s "$CALLS" ]
DEV=$DEV_SAVE
# no bootslot at all: logged, nothing written
echo 'console=ttyS0' > "$dir/proc/cmdline"; mkmisc 005; : > "$CALLS"; ! reset_tries 2>/dev/null; [ ! -s "$CALLS" ]
# healthy(): needs both dropbear and lan
pidof() { return 1; }; ! healthy
pidof() { return 0; }; ifstatus() { echo '{ "up": true }'; }; healthy
ifstatus() { echo '{ "up": false }'; }; ! healthy
echo "PASS: x28-bootok resets the A tries byte in all four copies, only on slot A, only on a boot-control record, and stops on failure"
