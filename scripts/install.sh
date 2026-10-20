#!/bin/sh
# Install the LuCI fixes on a ZLT X28 over SSH.
#
#   scripts/install.sh <ssh-host> <path/to/luci_fixed.tgz>
#
# <ssh-host> is anything `ssh` understands (an alias from ~/.ssh/config works).
# luci_fixed.tgz comes from https://github.com/EngineerMazeed/ZLT-X28
#
# Only adds/replaces the files listed in scripts/files.txt plus the overlay in
# router/. Backups of everything it overwrites go to /root/luci-backup on the router.
set -eu

HOST=${1:?usage: install.sh <ssh-host> <luci_fixed.tgz>}
TGZ=${2:?usage: install.sh <ssh-host> <luci_fixed.tgz>}
HERE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "== extracting upstream archive"
mkdir "$TMP/up"
tar xzf "$TGZ" -C "$TMP/up"

echo "== backing up files that will be replaced"
{ cat "$HERE/scripts/files.txt"
  (cd "$HERE/router" && find . -type f | sed 's|^\./||')
  echo usr/lib/lua/luci/dispatcher.lua; } |
ssh "$HOST" 'mkdir -p /root/luci-backup && cd / &&
  while read f; do [ -f "$f" ] && echo "$f"; done |
  tar cf /root/luci-backup/before-$(date +%Y%m%d-%H%M%S).tar -T - 2>/dev/null; true'

echo "== upstream LuCI files (theme, status/system/network/firewall views)"
(cd "$TMP/up" && tar cf - -T "$HERE/scripts/files.txt") | ssh "$HOST" 'cd / && tar xf -'

echo "== overlay: network ubus shim, ACLs, index.html redirect"
(cd "$HERE/router" && tar cf - .) | ssh "$HOST" 'cd / && tar xf -'

echo "== dispatcher.lua: no trailing slash on the root URL"
ssh "$HOST" 'cat /usr/lib/lua/luci/dispatcher.lua' > "$TMP/dispatcher.lua"
if grep -q 'if #path == 0 then' "$TMP/dispatcher.lua"; then
	(cd "$TMP" && mkdir -p a/usr/lib/lua/luci && cp dispatcher.lua a/usr/lib/lua/luci/ &&
	 patch -p1 -d a < "$HERE/patches/dispatcher-no-trailing-slash.patch")
	ssh "$HOST" 'cat > /usr/lib/lua/luci/dispatcher.lua' < "$TMP/a/usr/lib/lua/luci/dispatcher.lua"
else
	echo "   already patched"
fi

echo "== fixing ownership, clearing caches, reloading rpcd"
ssh "$HOST" 'chown -R root:root /www /usr/lib/lua/luci /usr/share/luci /usr/share/rpcd /usr/libexec/rpcd/network &&
  chmod 755 /usr/libexec/rpcd/network &&
  rm -rf /tmp/luci-indexcache /tmp/luci-modulecache &&
  /etc/init.d/rpcd restart'

echo "done. Open http://<router-ip>:4153/cgi-bin/luci (no trailing slash) and log in again."
