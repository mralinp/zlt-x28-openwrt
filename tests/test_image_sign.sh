#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# tools/build/image_sign.sh with throwaway keys: a signed image verifies against the trusted key, a changed one, an unsigned one and
# an unknown trusted key do not. Manual (needs docker and the bundle's rootfs): X28_ROOTFS=<...rootfs.tar.gz> sh tests/test_image_sign.sh
set -e
here=$(cd "$(dirname "$0")" && pwd); tool=$here/../tools/build/image_sign.sh
w=$(mktemp -d); trap 'rm -rf "$w"' EXIT; cd "$w"
IMG=${X28_SIGN_IMAGE:-x28-userspace:23.05.5}
docker image inspect "$IMG" >/dev/null 2>&1 || docker import --platform linux/arm64 "${X28_ROOTFS:?set X28_ROOTFS}" "$IMG" >/dev/null
mkdir keys other
docker run --rm --platform linux/arm64 -v "$w:/w" -w /w "$IMG" sh -c 'usign -G -c trusted -p keys/t.pub -s trusted.sec && cp keys/t.pub keys/$(usign -F -p keys/t.pub) && rm keys/t.pub && usign -G -c other -p o.pub -s o.sec && cp o.pub other/$(usign -F -p o.pub)'
sh "$tool" gen-signer "$w/signer" "$w/trusted.sec" >/dev/null
head -c 20000 /dev/urandom > image.bin
echo '{"supported_devices":["Tozed,X28"],"version":{"release":"test"}}' > meta.json
cp image.bin signed.bin; sh "$tool" sign signed.bin meta.json signer/signer.sec signer/signer.ucert >/dev/null
sh "$tool" verify signed.bin keys | grep -q 'signature OK'                                            # chain to the trusted key
sh "$tool" meta signed.bin | grep -q '"Tozed,X28"'                                                    # metadata readable
! sh "$tool" verify signed.bin other >/dev/null                                                       # a key the router does not trust
! sh "$tool" verify image.bin keys >/dev/null                                                          # unsigned
cp signed.bin bad.bin; printf 'X' | dd of=bad.bin bs=1 seek=100 conv=notrunc 2>/dev/null
! sh "$tool" verify bad.bin keys >/dev/null                                                            # changed after signing
echo "PASS: image_sign.sh signs with a certified signer key; changed, unsigned and untrusted images are refused"
