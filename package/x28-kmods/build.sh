#!/bin/bash
# Builds our modules for the vendor 4.19.205 kernel against the private SDK tree (#227, #198, #238). The SDK tree has
# no Module.symvers, so the modules carry no symbol versions; see docs/research/kernel-module-crc.md.
#
#   docker run --rm -v x28-kbuild:/k -v "$PWD/package/x28-kmods:/src:ro" -v "$PWD/private/kmods:/out" \
#     debian:bookworm bash /src/build.sh
#
# /k/linux is the configured SDK kernel tree (docs/BUILD.md). It stays private; only the sources here are public.
set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null
apt-get install -y -qq --no-install-recommends build-essential gcc-11 bc bison flex libssl-dev libelf-dev >/dev/null
cp -R /src/src /tmp/src
k() { make -C /k/linux ARCH=arm64 CC=gcc-11 HOSTCC=gcc-11 KCFLAGS='-w -fcommon -Wno-error' -j"$(nproc)" "$@" modules; }
k M=/tmp/src/tproxy
k M=/tmp/src/wireguard CONFIG_WIREGUARD=m
k M=/tmp/src/feed $(sed "s/\$/=m/" /tmp/src/feed/configs)
# The vendor kernel has the 5.x crypto library rework (crypto/chacha.h, lib/crypto/), so vanilla 4.19.205 sources do not
# build for it. These come from the private SDK tree, copied only into this container; the repo holds just src/sdk/Kbuild.
mkdir -p /tmp/sdk
for f in crypto/chacha_generic crypto/poly1305_generic crypto/chacha20poly1305 lib/crypto/libchacha lib/crypto/poly1305-donna64 lib/crypto/poly1305; do
	cp "/k/linux/$f.c" /tmp/sdk/
done
cp /k/linux/crypto/internal.h /src/src/sdk/Kbuild /tmp/sdk/
k M=/tmp/sdk CONFIG_CRYPTO_CHACHA20POLY1305=m CONFIG_CRYPTO_CHACHA20=m CONFIG_CRYPTO_POLY1305=m CONFIG_CRYPTO_LIB_CHACHA_GENERIC=m CONFIG_CRYPTO_LIB_POLY1305_GENERIC=m
mkdir -p /out/feed
for f in /tmp/sdk/*.ko; do
	strip --strip-debug -o "/out/feed/$(basename "$f")" "$f"
done
for f in /tmp/src/feed/*.ko; do
	strip --strip-debug -o "/out/feed/$(basename "$f")" "$f"
done
for f in /tmp/src/tproxy/*.ko /tmp/src/wireguard/wireguard.ko; do
	strip --strip-debug -o "/out/$(basename "$f")" "$f"
done
# The same files are the contents of the kmod-wireguard, kmod-ipt-tproxy and kmod-ipt-socket feed packages (#415).
cp /out/*.ko /out/feed/
cd /out && sha256sum *.ko | tee SHA256SUMS
