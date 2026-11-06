#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Cross-builds package/x28-nrband for the X28 (aarch64 musl, dynamic against the unit's libmipc_msg.so).
# Usage: tools/build/x28_nrband.sh <libmipc_msg.so from the device> <output dir>
# The library is only linked against, never copied; get it with: ssh x28 'cat /usr/lib/libmipc_msg.so' > libmipc_msg.so
set -eu
lib=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
out=$2
mkdir -p "$out"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp "$lib" "$work/libmipc_msg.so"
cp "$(dirname "$0")/../../package/x28-nrband/src/x28-nrband.c" "$work/"
docker run --rm --platform linux/arm64 -v "$work:/w" -w /w alpine:3.19 sh -c \
	'apk add --no-cache gcc musl-dev >/dev/null && gcc -O2 -Wall -o x28-nrband x28-nrband.c -L. -l:libmipc_msg.so -Wl,-rpath,/usr/lib'
cp "$work/x28-nrband" "$out/x28-nrband"
echo "built $out/x28-nrband"
