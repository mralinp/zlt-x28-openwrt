# Guest side: real nandsim flash + UBI + mtd-utils + busybox, the real x28.sh (only the vendor dd-nand is replaced).
ok() { echo "PASS $*"; }
bad() { echo "FAIL $*"; FAILED=1; }
t() { local n=$1; shift; if "$@"; then ok "$n"; else bad "$n"; fi; }
nt() { local n=$1; shift; if "$@"; then bad "$n"; else ok "$n"; fi; }
FAILED=0
insmod /mod/nandsim.ko first_id_byte=0xec second_id_byte=0xd3 third_id_byte=0x51 fourth_id_byte=0x26 parts=4,256,256 || { echo "FAIL nandsim"; cat /mod/order | sed "s/^/x28 mod /"; dmesg | tail -15 | sed "s/^/x28 dmesg /"; exit 1; }
sleep 1; echo "x28 /proc/mtd:"; cat /proc/mtd
ws=$(cat /sys/class/mtd/mtd1/writesize); es=$(cat /sys/class/mtd/mtd1/erasesize); echo "x28 writesize=$ws erasesize=$es"
mkdir -p /tmp/fp /x28/root/etc/init.d /x28/root/tmp /tmp/dump
printf 'dev:    size   erasesize  name\nmtd0: 00100000 %08x "misc"\nmtd1: 04000000 %08x "rootfs_a"\nmtd2: 04000000 %08x "rootfs_b"\n' $es $es $es > /tmp/fp/mtd
echo 'console=x bootslot=a' > /tmp/fp/cmdline; echo 'MemAvailable:   900000 kB' > /tmp/fp/meminfo
: > /x28/root/etc/init.d/x28-bootok; chmod +x /x28/root/etc/init.d/x28-bootok
cat > /usr/sbin/dd-nand <<'SH'
#!/bin/sh
for a in "$@"; do case $a in of=*) f=${a#of=};; seek=*) s=${a#seek=};; count=*) c=${a#count=};; esac; done
b=$((s / 262144 * 262144))
dd if="$f" of=/tmp/blk bs=262144 skip=$((b / 262144)) count=1 2>/dev/null
dd of=/tmp/blk bs=1 seek=$((s - b)) count=$c conv=notrunc 2>/dev/null
flash_erase "$f" $b 1 >/dev/null 2>&1 && nandwrite -s $b "$f" /tmp/blk >/dev/null 2>&1
SH
chmod +x /usr/sbin/dd-nand
mkimg() { # name content: a squashfs + empty data volume, built on mtd2 with ubi-utils and dumped, like a real slot image
	rm -rf /tmp/sq; mkdir -p /tmp/sq; echo "$2" > /tmp/sq/file; mksquashfs /tmp/sq /tmp/$1.sqfs -comp gzip -noappend >/dev/null 2>&1
	ubiformat /dev/mtd2 -y >/dev/null 2>&1; ubiattach /dev/ubi_ctrl -m 2 -d 5 >/dev/null 2>&1
	ubimkvol /dev/ubi5 -N rootfs -s 1MiB >/dev/null 2>&1; ubiupdatevol /dev/ubi5_0 /tmp/$1.sqfs >/dev/null 2>&1
	ubimkvol /dev/ubi5 -N rootfs_data -s 2MiB >/dev/null 2>&1; ubidetach -d 5 >/dev/null 2>&1
	dd if=/dev/mtd2 of=/tmp/$1.ubi bs=262144 2>/dev/null
}
mkimg old "old image"; mkimg new "new image"
[ -s /tmp/old.ubi ] && [ -s /tmp/new.ubi ] || { echo "FAIL ubinize"; exit 1; }
ubiformat /dev/mtd1 -y -f /tmp/old.ubi 2>&1 | sed 's/^/x28 ubiformat: /'; ubiattach /dev/ubi_ctrl -m 1 -d 0 2>&1 | sed 's/^/x28 ubiattach: /'; echo "x28 flash: $(dd if=/dev/mtd1 bs=16 count=1 2>/dev/null | hexdump -v -e '1/1 "%02x"')"; sleep 1; ls /dev | grep -E 'mtd|ubi' | tr '\n' ' ' | sed 's/^/x28 dev: /'; echo; dmesg | tail -12 | sed 's/^/x28 dmesg: /'
t "old image attached as ubi0" [ -e /dev/ubi0_0 ]
mkmisc() { # A entry, B entry as octal escapes
	dd if=/dev/zero bs=262144 count=4 2>/dev/null | tr '\000' '\377' > /tmp/misc.img
	for i in 0 1 2 3; do
		printf '\000AB0\377\377\377\377'"$1$2" | dd of=/tmp/misc.img bs=1 seek=$((2048 + 262144 * i)) conv=notrunc 2>/dev/null
	done
	flash_erase /dev/mtd0 0 0 2>&1 | sed 's/^/x28 flash_erase: /'; nandwrite -p /dev/mtd0 /tmp/misc.img 2>&1 | sed 's/^/x28 nandwrite: /'
}
entries() { for i in 0 1 2 3; do dd if=/dev/mtd0 bs=1 skip=$((2056 + 262144 * i)) count=8 2>/dev/null | hexdump -v -e '1/1 "%02x"'; printf ' '; done; }
mkmisc '\017\000\000\000' '\016\000\001\001'
t "misc starts as A 0f / B 0e" [ "$(entries)" = "0f0000000e000101 0f0000000e000101 0f0000000e000101 0f0000000e000101 " ]
mktar() { # tarball name, image name
	rm -rf /tmp/t; mkdir -p /tmp/t/sysupgrade-x28; cp /tmp/$2.ubi /tmp/t/sysupgrade-x28/root
	(cd /tmp/t/sysupgrade-x28 && sha256sum root | cut -d' ' -f1 > root.sha256
	 printf '%s %s\n' "$(sha256sum /tmp/$2.sqfs | cut -d' ' -f1)" "$(wc -c < /tmp/$2.sqfs)" > root.rootfs)
	(cd /tmp/t && tar -cf /tmp/$1.tar sysupgrade-x28)
}
mktar new new
export X28_UP_TEST=1 X28_UP_PROC=/tmp/fp X28_UP_DDNAND=/usr/sbin/dd-nand X28_UP_MISC=/dev/mtd0 X28_UP_ROOT=/x28/root X28_UP_TMP=/tmp X28_UP_DUMP=/tmp/dump X28_UP_SYS=/sys X28_UP_DEVDIR=/dev
. /x28/platform.sh
X28_UP_WRITE=x28_ubi_write; X28_UP_VERIFY=x28_ubi_verify
volhash() { # mtd, bytes: sha of the first bytes of volume 0 after attaching it as ubi4
	ubiattach /dev/ubi_ctrl -m $1 -d 4 >/dev/null 2>&1; sleep 1; head -c "$2" /dev/ubi4_0 | sha256sum | cut -d' ' -f1; ubidetach -d 4 >/dev/null 2>&1
}
newsha=$(sha256sum /tmp/new.sqfs | cut -d' ' -f1); newn=$(wc -c < /tmp/new.sqfs)

echo "x28 == 1. corrupt tarball: nothing changes"
(cd /tmp/t/sysupgrade-x28 && echo 0000 > root.sha256 && cd .. && tar -cf /tmp/bad.tar sysupgrade-x28)
before=$(entries)
nt "bad hash refused" platform_check_image /tmp/bad.tar
t "misc untouched" [ "$(entries)" = "$before" ]

echo "x28 == 2. in place on A (ubi0 attached, running)"
t "check passes" platform_check_image /tmp/new.tar
platform_do_upgrade /tmp/new.tar; rc=$?
t "upgrade rc=0" [ $rc -eq 0 ]
t "rootfs_a now holds the new squashfs" [ "$(volhash 1 $newn)" = "$newsha" ]
t "misc: A 0f tries 0, B unchanged" [ "$(entries)" = "0f0000000e000101 0f0000000e000101 0f0000000e000101 0f0000000e000101 " ]
t "dump saved, 1 MiB" [ "$(wc -c < "$(ls /tmp/dump/misc-* | head -1)")" -eq 1048576 ]

echo "x28 == 3. native B: write B, flip priorities"
mkimg old2 "second old"; ubiformat /dev/mtd2 -y -f /tmp/old2.ubi >/dev/null 2>&1; mktar newer new
: > /x28/root/etc/x28-native-b
before=$(entries)
nt "marker alone refused" platform_do_upgrade /tmp/newer.tar
t "misc untouched without confirmation" [ "$(entries)" = "$before" ]
: > /x28/root/tmp/x28-write-b-ok
platform_do_upgrade /tmp/newer.tar; rc=$?
t "upgrade rc=0" [ $rc -eq 0 ]
t "rootfs_b now holds the new squashfs" [ "$(volhash 2 $newn)" = "$newsha" ]
t "misc: B 0f tries 0, A 0e" [ "$(entries)" = "0e0000000f000101 0e0000000f000101 0e0000000f000101 0e0000000f000101 " ]

echo "x28 == 4. a failed write leaves misc alone"
mkmisc '\017\000\000\000' '\016\000\001\001'; before=$(entries)
ubiformat() { return 1; }
platform_do_upgrade /tmp/newer.tar 2>/dev/null; rc=$?
unset -f ubiformat
t "failure reported" [ $rc -ne 0 ]
t "misc untouched" [ "$(entries)" = "$before" ]
[ $FAILED -eq 0 ] && echo "PASS-ALL"
