#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# x28-packages-restore against a fake opkg: reinstall once per upgrade, retry while the feed is down, never pass options.
set -e
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
S=$(dirname "$0")/../package/x28-update/files/x28-packages-restore
fail() { echo "FAIL: $*"; exit 1; }
cat > "$t/opkg" <<'EOF'
#!/bin/sh
echo "$*" >> "$T/calls"
case "$1" in
	list-installed) sed 's/$/ - 1/' "$T/have" ;;
	update) [ ! -e "$T/offline" ] ;;
	list) case "$2" in kmod-good) echo "$2 - 1:4.19.205-x28 - stub"; echo "$2 - 5.15.167-1 - up" ;; kmod-*) echo "$2 - 5.15.167-1 - up" ;; esac ;;
	install) case "$2" in missing-in-feed) exit 255 ;; esac; echo "$2" >> "$T/have"; exit 255 ;;  # 255 even on success, like the unit
esac
EOF
chmod +x "$t/opkg"
export T="$t" X28_PR_LIST="$t/list" X28_PR_DONE="$t/done" X28_PR_OPKG="$t/opkg" X28_PR_TRIES=2 X28_PR_WAIT=0 X28_PR_LOCK="$t/lock" X28_PR_KREL=4.19.205
printf '#!/bin/sh\n' > "$t/logger"; chmod +x "$t/logger"
run() { : > "$t/calls"; PATH="$t:$PATH" sh "$S" >/dev/null 2>&1; }
printf 'base-files\trom\nmwan3\toverlay\nluci-app-mwan3\toverlay\n-oinject\toverlay\nkept\toverlay\n' > "$t/list"
printf 'base-files\nkept\n' > "$t/have"
sleep 1  # the marker must be newer than the list (1 s resolution)

# Feed down: nothing installed, no marker, so the next boot tries again.
touch "$t/offline"
run && fail 'offline run claimed success'
[ ! -e "$t/done" ] || fail 'marker set while the feed was unreachable'
grep -q '^install' "$t/calls" && fail 'installed without a feed'
# Feed up: the missing added packages come back, the invalid name is never passed, the marker is set.
rm "$t/offline"
run || fail 'restore failed'
grep -qx 'install mwan3' "$t/calls" && grep -qx 'install luci-app-mwan3' "$t/calls" || fail 'packages not reinstalled'
grep -q 'inject' "$t/calls" && fail 'an option-like name reached opkg'
grep -qx 'install kept' "$t/calls" && fail 'reinstalled a present package'
[ -e "$t/done" ] || fail 'marker not set'
# Once per upgrade: a package the owner removed afterwards stays removed.
sed -i.bak '/^mwan3$/d' "$t/have"
run; [ ! -s "$t/calls" ] || fail 'ran again after the marker'
# The next upgrade restores a newer list: it runs again.
sleep 1; touch "$t/list"
run; grep -qx 'install mwan3' "$t/calls" || fail 'new upgrade not handled'
# Kernel modules only from a build for the running kernel.
sleep 1; touch "$t/list"; printf 'kmod-good\toverlay\nkmod-other\toverlay\n' >> "$t/list"
run && fail 'a skipped kmod reported as success'
grep -qx 'install kmod-good' "$t/calls" || fail 'kmod for this kernel not installed'
grep -qx 'install kmod-other' "$t/calls" && fail 'kmod for another kernel installed'
# A failed install sets no marker: the next boot tries again.
[ ! -e "$t/done" ] || [ "$t/done" -ot "$t/list" ] || fail 'marker set after a failed install'
echo 'PASS: added packages reinstalled once per upgrade, retried while offline, names checked'
