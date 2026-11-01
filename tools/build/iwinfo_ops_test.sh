#!/bin/sh
# Every op iwinfo_cli's `info` calls unchecked must be set by wext (apcli0 falls to it) and mtwifi, or the CLI segfaults (#221).
# Needs only curl and git: it applies our patch to the pinned upstream source.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
COMMIT=$(sed -n 's/^IWINFO_COMMIT=\([0-9a-f]*\).*/\1/p' "$ROOT/tools/build/sdk_packages.sh")
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
curl -fsL "https://github.com/openwrt/iwinfo/archive/$COMMIT.tar.gz" | tar -C "$T" -xz --strip-components=1
git -C "$T" init -q && git -C "$T" apply "$ROOT/package/iwinfo-mtwifi/100-mtwifi-backend.patch"
fail=0
for op in $(sed -n '/^static void print_info/,/^}/p' "$T/iwinfo_cli.c" | grep -o 'print_[a-z_0-9]*(iw' | sed 's/print_//; s/(iw//' | sort -u); do
	case $op in	# print_x calls iw->x, except these
		type) continue;; center_chan1|center_chan2) continue;; # guarded by a NULL test
		rate) op=bitrate;; encryption) ;; mbssid_supp) op=mbssid_support;; hwmodes) op=hwmodelist;; hardware_id|hardware_name) ;;
	esac
	for f in wext mtwifi; do
		sed -n "/^const struct iwinfo_ops ${f}_ops/,/^};/p" "$T/iwinfo_$f.c" | grep -q "^[[:space:]]*\.$op[[:space:]]*=" ||
			{ echo "FAIL: ${f}_ops has no .$op" >&2; fail=1; }
	done
done
[ $fail = 0 ] && echo "ok: wext and mtwifi set every op iwinfo info calls"
exit $fail
