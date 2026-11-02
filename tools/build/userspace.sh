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
  uhttpd uhttpd-mod-ubus rpcd-mod-luci libustream-mbedtls px5g-mbedtls
  -dnsmasq dnsmasq-full libmnl0
  openvpn-openssl luci-app-openvpn xl2tpd ppp-mod-pptp wireguard-tools luci-proto-wireguard
  luci-app-passwall2 xray-core iptables-mod-tproxy iptables-mod-socket iptables-mod-iprange
  iptables-mod-conntrack-extra iptables-mod-extra"

# Passwall2 and xray come from the Passwall build feeds, signed with the key in package/x28-feed (#198).
PASSWALL=https://master.dl.sourceforge.net/project/openwrt-passwall-build/releases/packages-23.05/aarch64_generic
PASSWALL_KEY=0abda65a492b4887

OUT=$(mkdir -p "${1:-out}" && cd "${1:-out}" && pwd)
WORK=${WORK:-work}
mkdir -p "$WORK"
[ -f "$WORK/$IB.tar.xz" ] || curl -fL --retry 3 -o "$WORK/$IB.tar.xz" "$URL"
echo "$IB_SHA256  $WORK/$IB.tar.xz" | sha256sum -c -
[ -d "$WORK/$IB" ] || tar -C "$WORK" -xJf "$WORK/$IB.tar.xz"
grep -q '^src/gz passwall2 ' "$WORK/$IB/repositories.conf" ||
  sed -i "/^## This is the local package repository/i src/gz passwall2 $PASSWALL/passwall2\nsrc/gz passwall_packages $PASSWALL/passwall_packages\n" \
    "$WORK/$IB/repositories.conf"
cp "$(dirname "$0")/../../package/x28-feed/files/passwall.pub" "$WORK/$IB/keys/$PASSWALL_KEY"

# libiwinfo with the mtwifi backend (#165) and ubi-utils (#183): ImageBuilder installs local packages/ and prefers release 2.
"$(dirname "$0")/sdk_packages.sh" "$WORK/sdk"
mkdir -p "$WORK/$IB/packages"
cp "$WORK"/sdk/*.ipk "$WORK/$IB/packages/"

make -C "$WORK/$IB" image PROFILE=generic PACKAGES="$(echo $PACKAGES)" BIN_DIR="$OUT"

# The rootfs carries armsr's 5.15 kernel modules from dependencies; the X28 assembly replaces them.
ls -l "$OUT"
grep -q '^libiwinfo20230701 - 2023-07-01-ca79f641-3$' "$OUT"/*.manifest ||
  { echo "the image did not take the mtwifi libiwinfo" >&2; exit 1; }
# The preinit hook relies on this block's extroot behaviour (#183).
grep -q '^ubi-utils - ' "$OUT"/*.manifest && grep -q '^block-mount - 2023-02-28-bfe882d5-' "$OUT"/*.manifest ||
  { echo "the image lacks ubi-utils or the expected block-mount" >&2; exit 1; }
# Our dnsmasq-full has ipset and no nftset (#203): the feed's build would pull nftables-json in.
grep -q '^dnsmasq-full - .*-x28$' "$OUT"/*.manifest || { echo "the image did not take our dnsmasq-full" >&2; exit 1; }
grep -q '^luci-app-passwall2 - ' "$OUT"/*.manifest && grep -q '^xray-core - ' "$OUT"/*.manifest ||
  { echo "the image lacks Passwall2 or xray" >&2; exit 1; }
if grep -qE '^(firewall4|nftables[a-z-]*) ' "$OUT"/*.manifest; then
  echo "firewall4/nftables ended up in the image" >&2
  exit 1
fi
