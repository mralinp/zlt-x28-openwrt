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
# firewall4, and the LuCI pages that do not depend on firewall4 (docs/FIRMWARE-INVENTORY.md).
PACKAGES="-firewall4 -nftables -kmod-nft-offload
  firewall iptables-legacy ip6tables-legacy
  luci-base luci-mod-admin-full luci-theme-bootstrap luci-app-opkg
  uhttpd uhttpd-mod-ubus rpcd-mod-luci"

OUT=$(mkdir -p "${1:-out}" && cd "${1:-out}" && pwd)
WORK=${WORK:-work}
mkdir -p "$WORK"
[ -f "$WORK/$IB.tar.xz" ] || curl -fL --retry 3 -o "$WORK/$IB.tar.xz" "$URL"
echo "$IB_SHA256  $WORK/$IB.tar.xz" | sha256sum -c -
[ -d "$WORK/$IB" ] || tar -C "$WORK" -xJf "$WORK/$IB.tar.xz"

make -C "$WORK/$IB" image PROFILE=generic PACKAGES="$(echo $PACKAGES)" BIN_DIR="$OUT"

# The rootfs carries armsr's 5.15 kernel modules from dependencies; the X28 assembly replaces them.
ls -l "$OUT"
if grep -qE '^(firewall4|nftables[a-z-]*) ' "$OUT"/*.manifest; then
  echo "firewall4/nftables ended up in the image" >&2
  exit 1
fi
