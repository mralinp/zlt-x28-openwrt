#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Sign and verify sysupgrade images the way OpenWrt's fwtool/ucert expect (#476). Runs OpenWrt's own aarch64 tools in a container
# made from the 23.05.5 userspace rootfs (docker import), so it works on a Mac and on CI (qemu-user on x86).
#
#   image_sign.sh gen-signer OUTDIR TRUSTED_SEC   a new image-signing key and a ucert certificate for it, issued by TRUSTED_SEC (the
#                                                 feed key, kept offline): OUTDIR/signer.sec signer.pub signer.ucert
#   image_sign.sh sign IMAGE META.json SIGNER_SEC SIGNER_UCERT
#                                                 append the metadata, sign, append the certificate (in place)
#   image_sign.sh verify IMAGE KEYS_DIR           what the router does: certificate chain to a key in KEYS_DIR (/etc/opkg/keys)
#   image_sign.sh meta IMAGE                      print the metadata
#
# Needs: docker, curl, and X28_ROOTFS=<openwrt-23.05.5-armsr-armv8-rootfs.tar.gz> (the one in the release bundle) on first use.
# The router needs `ucert` (verify); signing here needs `ucert-full`, pinned below.
set -e
IMG=${X28_SIGN_IMAGE:-x28-userspace:23.05.5}
CACHE=${X28_SIGN_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/x28-sign}
UCERT_FULL=ucert-full_2020-05-24-00b921d8-1_aarch64_generic.ipk
UCERT_FULL_SHA=e83b18bb5a892de759890c047e24fdc31e01905e5008b50e3739850238a33e9a
URL=https://downloads.openwrt.org/releases/23.05.5/packages/aarch64_generic/base/$UCERT_FULL

die() { echo "image_sign: $*" >&2; exit 1; }

prepare() {
	mkdir -p "$CACHE"
	if ! docker image inspect "$IMG" >/dev/null 2>&1; then
		[ -f "${X28_ROOTFS:-}" ] || die "set X28_ROOTFS to the bundle's openwrt-23.05.5-armsr-armv8-rootfs.tar.gz"
		docker import --platform linux/arm64 "$X28_ROOTFS" "$IMG" >/dev/null
	fi
	if [ ! -x "$CACHE/ucert" ]; then
		[ -f "$CACHE/$UCERT_FULL" ] || curl -fsSL -o "$CACHE/$UCERT_FULL" "$URL"
		echo "$UCERT_FULL_SHA  $CACHE/$UCERT_FULL" | shasum -a 256 -c - >/dev/null || die "$UCERT_FULL does not match its pinned hash"
		d=$(mktemp -d); (cd "$d" && tar -xzf "$CACHE/$UCERT_FULL" && tar -xzf data.tar.gz) && cp "$d/usr/bin/ucert" "$CACHE/ucert" && chmod 755 "$CACHE/ucert"
		rm -rf "$d"
	fi
}

# run <workdir> <command...>: the workdir is /w, the cached ucert-full is /usr/bin/ucert
run() {
	w=$1; shift
	docker run --rm --platform linux/arm64 -v "$w:/w" -v "$CACHE/ucert:/usr/bin/ucert:ro" -w /w "$IMG" "$@"
}

abs() { case "$1" in /*) echo "$1" ;; *) echo "$(pwd)/$1" ;; esac; }

cmd=${1:-}; [ $# -gt 0 ] && shift
case "$cmd" in
gen-signer)
	[ $# -eq 2 ] || die "usage: gen-signer OUTDIR TRUSTED_SEC"
	out=$(abs "$1"); sec=$(abs "$2"); mkdir -p "$out"
	[ -f "$sec" ] || die "no such key: $2"
	[ ! -e "$out/signer.sec" ] || die "$out/signer.sec exists"
	prepare
	t=$(mktemp -d); cp "$sec" "$t/trusted.sec"
	run "$t" sh -c 'usign -G -c "X28 image signer" -p signer.pub -s signer.sec && ucert -I -c signer.ucert -p signer.pub -s trusted.sec'
	cp "$t/signer.sec" "$t/signer.pub" "$t/signer.ucert" "$out/"; chmod 600 "$out/signer.sec"; rm -rf "$t"
	echo "signer key and certificate in $out (the certificate is valid for one year; keep signer.sec secret)"
	;;
sign)
	[ $# -eq 4 ] || die "usage: sign IMAGE META.json SIGNER_SEC SIGNER_UCERT"
	image=$(abs "$1"); meta=$(abs "$2"); sec=$(abs "$3"); crt=$(abs "$4")
	prepare
	t=$(mktemp -d); cp "$image" "$t/img"; cp "$meta" "$t/meta.json"; cp "$sec" "$t/signer.sec"; cp "$crt" "$t/signer.ucert"
	run "$t" sh -c 'fwtool -I meta.json img && cp img msg && usign -S -m msg -s signer.sec -x signer.sig && { ucert -A -c signer.ucert -x signer.sig || true; } && ucert -D -c signer.ucert | grep -q "signed by" && fwtool -S signer.ucert img'
	cp "$t/img" "$image"; rm -rf "$t"
	echo "signed $1"
	;;
verify)
	[ $# -eq 2 ] || die "usage: verify IMAGE KEYS_DIR"
	image=$(abs "$1"); keys=$(abs "$2"); prepare
	t=$(mktemp -d); cp "$image" "$t/img"; mkdir "$t/keys"; cp "$keys"/* "$t/keys/"
	if run "$t" sh -c 'fwtool -q -s /tmp/c.ucert img && fwtool -q -T -s /dev/null img | ucert -V -q -m - -c /tmp/c.ucert -P keys'; then echo "signature OK"; rc=0; else echo "signature NOT valid"; rc=1; fi
	rm -rf "$t"; exit $rc
	;;
meta)
	[ $# -eq 1 ] || die "usage: meta IMAGE"
	image=$(abs "$1"); prepare; t=$(mktemp -d); cp "$image" "$t/img"
	run "$t" sh -c 'fwtool -q -i /tmp/m img && cat /tmp/m'; echo; rm -rf "$t"
	;;
*) die "usage: image_sign.sh gen-signer|sign|verify|meta (see the header)" ;;
esac
