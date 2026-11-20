#!/usr/bin/env bash
# Build what the 23.05.5 feeds lack for the X28, with the official SDK:
# - iwinfo 2023-07-01 with our mtwifi backend (package/iwinfo-mtwifi, #165): mt_wifi has no nl80211, and without this LuCI
#   has no channel list or associated stations. Release 2 makes ImageBuilder prefer it over the feed's.
# - ubi-utils (#183): to attach user_data. The armsr target has no raw flash, so the feeds skip it (@NAND_SUPPORT).
# - dnsmasq-full with ipset and no nftset (#203): the vendor kernel has no nftables, and the feed's build needs it.
# Runs on Linux x86_64, like userspace.sh.
#
#   tools/build/sdk_packages.sh OUT_DIR
set -euo pipefail

VERSION=23.05.5
SDK=openwrt-sdk-$VERSION-armsr-armv8_gcc-12.3.0_musl.Linux-x86_64
SDK_SHA256=8a6008388911dfaa10789c1266c0bc7166576d898b6764da7471b4df66abc55e  # from the release sha256sums
URL=https://downloads.openwrt.org/releases/$VERSION/targets/armsr/armv8/$SDK.tar.xz
IWINFO_COMMIT=ca79f64154b107f192ec3c1ba631816cb8b07922  # the libiwinfo20230701 ABI the feed's rpcd-mod-iwinfo expects

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
OUT=$(mkdir -p "$1" && cd "$1" && pwd)
WORK=${WORK:-work}
mkdir -p "$WORK"
[ -f "$WORK/$SDK.tar.xz" ] || curl -fL --retry 3 -o "$WORK/$SDK.tar.xz" "$URL"
echo "$SDK_SHA256  $WORK/$SDK.tar.xz" | sha256sum -c -
[ -d "$WORK/$SDK" ] || tar -C "$WORK" -xJf "$WORK/$SDK.tar.xz"

cd "$WORK/$SDK"
./scripts/feeds update base >/dev/null
./scripts/feeds install iwinfo mtd-utils dnsmasq >/dev/null
P=feeds/base/package/network/utils/iwinfo
grep -q "^PKG_SOURCE_VERSION:=$IWINFO_COMMIT" $P/Makefile || { echo "iwinfo in the 23.05 feed moved off $IWINFO_COMMIT" >&2; exit 1; }
mkdir -p $P/patches
cp "$ROOT/package/iwinfo-mtwifi/100-mtwifi-backend.patch" $P/patches/
sed -i -e 's/^PKG_RELEASE:=1$/PKG_RELEASE:=4/' -e 's/BACKENDS="nl80211"/BACKENDS="nl80211 mtwifi"/' $P/Makefile
grep -q '^PKG_RELEASE:=4$' $P/Makefile && grep -q 'BACKENDS="nl80211 mtwifi"' $P/Makefile
M=feeds/base/package/utils/mtd-utils/Makefile
grep -q '@NAND_SUPPORT' $M && sed -i 's/@NAND_SUPPORT *//' $M
D=feeds/base/package/network/services/dnsmasq/Makefile
sed -i -E 's/^PKG_RELEASE:=(.*)$/PKG_RELEASE:=\1-x28/' $D
# The ipset utility comes from the X28 feed, for the module subset the kernel has; kmod-ipt-ipset can't be satisfied.
sed -i 's/+PACKAGE_dnsmasq_full_ipset:kmod-ipt-ipset *//' $D
grep -q '^PKG_RELEASE:=.*-x28$' $D && ! grep -q 'kmod-ipt-ipset' $D
make defconfig >/dev/null
sed -i -e '/ubi-utils/d' -e '/dnsmasq/d' .config
cat >> .config <<'CONFIG'
CONFIG_PACKAGE_dnsmasq-full=m
CONFIG_PACKAGE_dnsmasq_full_ipset=y
# CONFIG_PACKAGE_dnsmasq_full_nftset is not set
CONFIG
echo CONFIG_PACKAGE_ubi-utils=m >> .config
make defconfig >/dev/null
make package/iwinfo/compile package/mtd-utils/compile package/dnsmasq/compile -j1 >"$OUT/sdk-build.log" 2>&1 || { tail -40 "$OUT/sdk-build.log" >&2; exit 1; }
find bin \( -name '*iwinfo*_2023-07-01-ca79f641-4_*.ipk' -o -name 'ubi-utils_*.ipk' -o -name 'dnsmasq-full_*-x28_*.ipk' \) -exec cp {} "$OUT/" \;
ls "$OUT"/libiwinfo20230701_2023-07-01-ca79f641-4_*.ipk "$OUT"/ubi-utils_*.ipk "$OUT"/dnsmasq-full_*-x28_*.ipk
