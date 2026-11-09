#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# package/x28-update's check against a fake fetcher (a file standing in for the GitHub API); no network, no device.
set -e
dir=$(mktemp -d); trap 'rm -rf "$dir"' EXIT
check="$(dirname "$0")/../package/x28-update/files/x28-update-check"
export X28_UPD_CACHE=$dir/cache X28_UPD_RELEASE=$dir/release X28_UPD_FETCH="cat $dir/api"
run() { rm -f "$dir/cache"; sh "$check"; }
# compact JSON as the API sends it; 0.77.0 has only the unsigned tarball, 0.10.0 sorts above 0.9.0
printf '[{"tag_name":"v0.77.0","assets":[{"name":"x28-sysupgrade-0.77.0-unsigned.tar"}]},{"assets":[{"name":"x28-sysupgrade-0.10.0.tar","browser_download_url":"x"},{"name":"x28-sysupgrade-0.10.0.tar.sha256"}]},{"assets":[{"name":"x28-sysupgrade-0.9.0.tar"}]}]' > "$dir/api"

echo 0.9.0 > "$dir/release"
out=$(run); echo "$out" | grep -q '"latest":"0.10.0","newer":true,'
echo "$out" | grep -q '"url":"https://github.com/mralinp/zlt-x28-openwrt/releases/download/v0.10.0/x28-sysupgrade-0.10.0.tar"'
echo 0.10.0 > "$dir/release"; run | grep -q '"newer":false'
echo 0.11.0 > "$dir/release"; run | grep -q '"newer":false'
rm "$dir/release"; run | grep -q '"current":"","latest":"0.10.0","newer":true'
# cached: a changed API is not asked again within the period
echo 0.10.0 > "$dir/release"; run >/dev/null; : > "$dir/api"; sh "$check" | grep -q '"latest":"0.10.0"'
# no signed image, or the fetch fails: no notice, and the error is cached too
run | grep -q '"error"'; X28_UPD_FETCH=false run | grep -q '"error"'
run | grep -q newer && exit 1
echo "x28-update: ok"
