#!/usr/bin/env bash
# Build the OpenWrt 23.05 userspace rootfs for the X28: the open half of the native image.
# Official prebuilt packages only; no vendor files (those are added locally, see docs/BUILD.md).
# Runs on Linux x86_64 (CI, a workstation, or `docker --platform linux/amd64`).
#
#   tools/build/userspace.sh [OUT_DIR]        # default: out/
set -euo pipefail

VERSION=23.05.5
IB=openwrt-imagebuilder-$VERSION-armsr-armv8.Linux-x86_64
IB_SHA256=af89b96dfd1b370197a907774d97be1732a0c8cb7c58f0048b86e477e287c2b4  # from the release sha256sums
URL=https://downloads.openwrt.org/releases/$VERSION/targets/armsr/armv8/$IB.tar.xz

# The stock X28 kernel (4.19) has no nf_tables: use the iptables firewall (fw3) instead of
# firewall4. luci-app-firewall only needs uci-firewall, which fw3 provides (#164).
PACKAGES="-firewall4 -nftables -kmod-nft-offload
  firewall iptables-legacy ip6tables-legacy
  luci-base luci-mod-admin-full luci-theme-bootstrap luci-app-opkg
  luci-app-firewall luci-proto-ipv6 luci-proto-ppp
  iwinfo rpcd-mod-iwinfo block-mount ubi-utils
  uhttpd uhttpd-mod-ubus rpcd-mod-luci"

OUT=$(mkdir -p "${1:-out}" && cd "${1:-out}" && pwd)
WORK=${WORK:-work}
mkdir -p "$WORK"
[ -f "$WORK/$IB.tar.xz" ] || curl -fL --retry 3 -o "$WORK/$IB.tar.xz" "$URL"
echo "$IB_SHA256  $WORK/$IB.tar.xz" | sha256sum -c -
[ -d "$WORK/$IB" ] || tar -C "$WORK" -xJf "$WORK/$IB.tar.xz"

# libiwinfo with the mtwifi backend (#165) and ubi-utils (#183): ImageBuilder installs local packages/ and prefers release 2.
"$(dirname "$0")/sdk_packages.sh" "$WORK/sdk"
mkdir -p "$WORK/$IB/packages"
cp "$WORK"/sdk/*.ipk "$WORK/$IB/packages/"

make -C "$WORK/$IB" image PROFILE=generic PACKAGES="$(echo $PACKAGES)" BIN_DIR="$OUT"

# The rootfs carries armsr's 5.15 kernel modules from dependencies; the X28 assembly replaces them.
ls -l "$OUT"
grep -q '^libiwinfo20230701 - 2023-07-01-ca79f641-2$' "$OUT"/*.manifest ||
  { echo "the image did not take the mtwifi libiwinfo" >&2; exit 1; }
grep -qE '^(ubi-utils|block-mount) ' "$OUT"/*.manifest && [ "$(grep -cE '^(ubi-utils|block-mount) ' "$OUT"/*.manifest)" = 2 ] ||
  { echo "the image lacks ubi-utils or block-mount" >&2; exit 1; }
if grep -qE '^(firewall4|nftables[a-z-]*) ' "$OUT"/*.manifest; then
  echo "firewall4/nftables ended up in the image" >&2
  exit 1
fi
