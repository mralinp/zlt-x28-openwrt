#!/usr/bin/env bash
# Build iwinfo 2023-07-01 with our mtwifi backend (package/iwinfo-mtwifi, #165) using the official 23.05.5 SDK.
# mt_wifi has no nl80211; without this LuCI has no channel list or associated stations for the X28 radios.
# The release is bumped to 2 so ImageBuilder prefers these packages over the feed's.
# Runs on Linux x86_64, like userspace.sh.
#
#   tools/build/iwinfo_mtwifi.sh OUT_DIR
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
./scripts/feeds install iwinfo >/dev/null
P=feeds/base/package/network/utils/iwinfo
grep -q "^PKG_SOURCE_VERSION:=$IWINFO_COMMIT" $P/Makefile || { echo "iwinfo in the 23.05 feed moved off $IWINFO_COMMIT" >&2; exit 1; }
mkdir -p $P/patches
cp "$ROOT/package/iwinfo-mtwifi/100-mtwifi-backend.patch" $P/patches/
sed -i -e 's/^PKG_RELEASE:=1$/PKG_RELEASE:=2/' -e 's/BACKENDS="nl80211"/BACKENDS="nl80211 mtwifi"/' $P/Makefile
grep -q '^PKG_RELEASE:=2$' $P/Makefile && grep -q 'BACKENDS="nl80211 mtwifi"' $P/Makefile
make defconfig >/dev/null
make package/iwinfo/compile -j1 >"$OUT/iwinfo-build.log" 2>&1 || { tail -40 "$OUT/iwinfo-build.log" >&2; exit 1; }
find bin -name '*iwinfo*_2023-07-01-ca79f641-2_*.ipk' -exec cp {} "$OUT/" \;
ls "$OUT"/libiwinfo20230701_2023-07-01-ca79f641-2_*.ipk
