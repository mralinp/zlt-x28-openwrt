#!/bin/sh
# Install the LuCI fixes and the router/ overlay on a ZLT X28 over SSH.
#
#   scripts/install.sh [-n] <ssh-host> <path/to/luci_fixed.tgz>
#
# <ssh-host> is anything `ssh` understands (an alias from ~/.ssh/config works).
# luci_fixed.tgz comes from https://github.com/EngineerMazeed/ZLT-X28
# -n  dry run: build every tar stream and check it (owner root, no ._* files), but do not touch the router.
#
# Only adds/replaces the files listed in scripts/files.txt plus every file under router/.
# Backups of everything it overwrites go to /root/luci-backup on the router.
# Services are never enabled or started here (templog, vendorsync, ...): do that by hand.
set -eu

DRY=0
[ "${1:-}" = "-n" ] && { DRY=1; shift; }
HOST=${1:?usage: install.sh [-n] <ssh-host> <luci_fixed.tgz>}
TGZ=${2:?usage: install.sh [-n] <ssh-host> <luci_fixed.tgz>}
HERE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Streams must be owned by root and carry no macOS metadata: plain tar on macOS leaves ._* files and
# your own uid on the router (and tar of "." also rewrites the owner of directories like /etc and /usr).
if tar --version 2>/dev/null | grep -q GNU; then
	TAROPTS="--owner=0 --group=0"
else
	TAROPTS="--uid 0 --gid 0 --uname root --gname root --no-xattrs"
fi
pack() { COPYFILE_DISABLE=1 tar $TAROPTS -cf - "$@"; }

# Read a tar stream on stdin: extract on the router, or in a dry run just verify it.
send() {
	if [ "$DRY" = 1 ]; then
		tar tvf - > "$TMP/list"
		n=$(($(wc -l < "$TMP/list")))   # $(( )) strips the padding BSD wc adds
		bad=$(($(awk '$3 != "root" && $3 != "0"' "$TMP/list" | wc -l)))
		dots=$(($(grep -c '/\._\|^\._' "$TMP/list" || true)))
		echo "   dry run: $n entries, $bad not owned by root, $dots ._* files"
		[ "$bad" = 0 ] && [ "$dots" = 0 ] || { echo "   refusing: bad stream" >&2; exit 1; }
	else
		ssh "$HOST" 'cd / && tar xf -'
	fi
}

# Files only (no directory entries), so existing directories keep their owner and mode.
overlay_files() { (cd "$HERE/router" && find . -type f ! -name '._*' ! -name .DS_Store | sed 's|^\./||' | sort); }

echo "== extracting upstream archive"
mkdir "$TMP/up"
tar xzf "$TGZ" -C "$TMP/up"

echo "== backing up files that will be replaced"
if [ "$DRY" = 1 ]; then
	echo "   dry run: skipped (would back up $(($(wc -l < "$HERE/scripts/files.txt"))) upstream + $(($(overlay_files | wc -l))) overlay files + dispatcher.lua)"
else
	{ cat "$HERE/scripts/files.txt"
	  overlay_files
	  echo usr/lib/lua/luci/dispatcher.lua; } |
	ssh "$HOST" 'mkdir -p /root/luci-backup && cd / &&
	  while read f; do [ -f "$f" ] && echo "$f"; done |
	  tar cf /root/luci-backup/before-$(date +%Y%m%d-%H%M%S).tar -T - 2>/dev/null; true'
fi

echo "== upstream LuCI files (theme, status/system/network/firewall views)"
(cd "$TMP/up" && pack -T "$HERE/scripts/files.txt") | send

echo "== overlay: everything under router/ (bridge, vendor pages, adapter, init scripts, ACLs, index.html)"
overlay_files > "$TMP/overlay.txt"
(cd "$HERE/router" && pack -T "$TMP/overlay.txt") | send

if [ "$DRY" = 1 ]; then
	echo "== dry run finished: nothing was sent to $HOST"
	exit 0
fi

echo "== dispatcher.lua: no trailing slash on the root URL"
ssh "$HOST" 'cat /usr/lib/lua/luci/dispatcher.lua' > "$TMP/dispatcher.lua"
if grep -q 'if #path == 0 then' "$TMP/dispatcher.lua"; then
	(cd "$TMP" && mkdir -p a/usr/lib/lua/luci && cp dispatcher.lua a/usr/lib/lua/luci/ &&
	 patch -p1 -d a < "$HERE/patches/dispatcher-no-trailing-slash.patch")
	ssh "$HOST" 'cat > /usr/lib/lua/luci/dispatcher.lua' < "$TMP/a/usr/lib/lua/luci/dispatcher.lua"
else
	echo "   already patched"
fi

echo "== script permissions, clearing caches, reloading rpcd"
ssh "$HOST" 'chmod 755 /usr/libexec/rpcd/network /usr/bin/vendorsync /usr/bin/voicectl /usr/bin/templog \
    /etc/init.d/vendorsync /etc/init.d/templog 2>/dev/null
  rm -rf /tmp/luci-indexcache /tmp/luci-modulecache &&
  /etc/init.d/rpcd restart'

echo "done. Open http://<router-ip>:4153/cgi-bin/luci (no trailing slash) and log in again."
