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
k M=/tmp/src/feed CONFIG_NET_ACT_GACT=m
mkdir -p /out/feed
for f in /tmp/src/feed/*.ko; do
	strip --strip-debug -o "/out/feed/$(basename "$f")" "$f"
done
for f in /tmp/src/tproxy/*.ko /tmp/src/wireguard/wireguard.ko; do
	strip --strip-debug -o "/out/$(basename "$f")" "$f"
done
cd /out && sha256sum *.ko | tee SHA256SUMS
