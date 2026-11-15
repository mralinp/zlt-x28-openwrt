#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# The /usr/sbin/wget wrapper (#616) against stub curl and uclient-fetch: opkg's form goes to curl, everything else to uclient-fetch untouched.
set -e
dir=$(mktemp -d); trap 'rm -rf "$dir"' EXIT
for p in curl uclient-fetch; do printf '#!/bin/sh\nprintf "%%s" "%s" > "$CALLS"; for a in "$@"; do printf " [%%s]" "$a" >> "$CALLS"; done\n' "$p" > "$dir/$p"; chmod +x "$dir/$p"; done
sed "s#/bin/uclient-fetch#$dir/uclient-fetch#g" "$(dirname "$0")/../package/x28-update/files/wget-curl" > "$dir/wget"; chmod +x "$dir/wget"
export CALLS="$dir/calls" PATH="$dir:$PATH"
U=https://github.com/o/r/releases/download/feed-3/Packages.gz
is() { "$dir/wget" "$@"; got=$(cat "$CALLS"); [ "$got" = "$want" ] || { echo "FAIL: wget $*"; echo " want: $want"; echo "  got: $got"; exit 1; }; }

want="curl [-fsSL] [--connect-timeout] [20] [--max-time] [300] [--retry] [2] [-o] [/tmp/a b] [$U]"; is -q -O "/tmp/a b" "$U"
want="curl [-fsSL] [-k] [--connect-timeout] [20] [--max-time] [45] [--retry] [2] [-o] [/tmp/p] [$U]"; is -q --no-check-certificate --timeout 45 -Y on -O /tmp/p "$U"
# Not opkg's form: sysupgrade's joined -O, an unknown option, no output file, two URLs.
want="uclient-fetch [-O/tmp/sysupgrade.img] [$U]"; is -O/tmp/sysupgrade.img "$U"
want="uclient-fetch [--spider] [-q] [$U]"; is --spider -q "$U"
want="uclient-fetch [-q] [$U]"; is -q "$U"
want="uclient-fetch [-q] [-O] [/tmp/p] [$U] [$U]"; is -q -O /tmp/p "$U" "$U"
echo 'WGET-CURL PASS'
