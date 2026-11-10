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

# x28-upgrade against the same fake API, a fake platform.sh, a fake fetcher and a fake sysupgrade (records its calls); no device.
up="$(dirname "$0")/../package/x28-update/files/x28-upgrade"
printf '[{"assets":[{"name":"x28-sysupgrade-0.10.0.tar"}]}]' > "$dir/api"; echo 0.9.0 > "$dir/release"
echo image > "$dir/image"
cat > "$dir/platform.sh" <<'P'
X28_MIN_FREE_KB=1
x28_misc_dev() { echo misc; }
x28_tries_zero() { [ -z "$TRIES" ]; }
x28_target() { echo "b 1"; }
x28_mtd_of_size() { echo "${SLOT:-1024}"; }
P
cat > "$dir/get" <<'G'
case "$2" in *.sha256) echo "${SUM:-$(sha256sum "$D/image" 2>/dev/null || shasum -a 256 "$D/image")}" | cut -d' ' -f1 ;; *) cp "$D/image" "$1" ;; esac
G
cat > "$dir/sysupgrade" <<'S'
echo "$*" >> "$D/calls"; [ "$1" != -T ] || [ -z "$FAIL_T" ]
S
mkdir "$dir/t"; D=$dir; export D
export X28_UPG_CHECK="sh $check" X28_UPG_PLATFORM=$dir/platform.sh X28_UPG_GET="sh $dir/get" X28_UPG_SYSUPGRADE="sh $dir/sysupgrade" X28_UPG_TMP=$dir/t
command -v sha256sum >/dev/null || sha256sum() { shasum -a 256 "$@"; }
upg() { rm -f "$dir/cache" "$dir/calls"; sh "$up" "$@"; }
upg | grep -q "running 0.9.0, newest signed image 0.10.0" && [ ! -e "$dir/calls" ]    # check only: nothing downloaded or run
upg -x 2>/dev/null && exit 1
upg -y | grep -q 'flashing 0.10.0 to slot b' && [ "$(cat "$dir/calls")" = "-T $dir/t/x28-sysupgrade-0.10.0.tar
-k -u $dir/t/x28-sysupgrade-0.10.0.tar" ]   # -k: settings and the package list are kept (#477)
# The default downloader follows redirects, reports HTTP errors and keeps the output-file calling convention.
mkdir "$dir/bin"
cat > "$dir/bin/curl" <<'C'
#!/bin/sh
[ "$1 $2 $3 $4 $5 $6 $7" = '-fL -sS --connect-timeout 30 --retry 2 -o' ] || exit 2
shift 7
exec sh "$D/get" "$@"
C
chmod +x "$dir/bin/curl"
(PATH="$dir/bin:$PATH"; unset X28_UPG_GET; upg -y) | grep -q 'flashing 0.10.0'
echo 0.10.0 > "$dir/release"; upg -y | grep -q 'up to date' && [ ! -e "$dir/calls" ]; echo 0.9.0 > "$dir/release"
TRIES=1 upg -y 2>/dev/null | grep -q 'FAILED: the running slot' && [ ! -e "$dir/calls" ]
SLOT=$((1 << 40)) upg -y | grep -q 'FAILED: /tmp has' && [ ! -e "$dir/calls" ]
SUM=0000 upg -y | grep -q 'FAILED: SHA-256' && [ ! -e "$dir/calls" ] && [ ! -e "$dir/t/x28-sysupgrade-0.10.0.tar" ]
FAIL_T=1 upg -y | grep -q 'FAILED: sysupgrade -T' && [ "$(cat "$dir/calls")" = "-T $dir/t/x28-sysupgrade-0.10.0.tar" ]
printf '[]' > "$dir/api"; upg -y | grep -q 'FAILED: no release'
mkdir "$dir/t/x28-upgrade.lock"; upg -y | grep -q 'FAILED: an upgrade is already running' && [ ! -e "$dir/calls" ]; rmdir "$dir/t/x28-upgrade.lock"
# a crafted cache cannot steer the download path or URL
echo '{"current":"0.9.0","latest":"../../x","newer":true}' > "$dir/cache"; sh "$up" -y | grep -q 'FAILED: bad version'
# -b: the background run ends its log with the outcome; the lock is gone afterwards
printf '[{"assets":[{"name":"x28-sysupgrade-0.10.0.tar"}]}]' > "$dir/api"; rm -f "$dir/cache" "$dir/calls"; sh "$up" -y -b | grep -q started
i=0; until grep -q 'flashing\|FAILED' "$dir/t/x28-upgrade.log" 2>/dev/null || [ $i -ge 50 ]; do i=$((i + 1)); sleep 0.1; done
tail -n 1 "$dir/t/x28-upgrade.log" | grep -q 'flashing 0.10.0'
i=0; while [ -e "$dir/t/x28-upgrade.lock" ] && [ $i -lt 50 ]; do i=$((i + 1)); sleep 0.1; done; [ ! -e "$dir/t/x28-upgrade.lock" ]
echo "x28-upgrade: ok"
