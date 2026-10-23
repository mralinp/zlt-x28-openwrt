#!/bin/sh
set -eu
backup=${1:-/root/x28-network-ui-backup-20261021}
test -f "$backup/controllers.tgz"
tar -xzf "$backup/controllers.tgz" -C /
if test -f "$backup/vendor-js.htm"; then
 cp -p "$backup/vendor-js.htm" /usr/lib/lua/luci/view/vendor/_js.htm
fi
rm -f /tmp/luci-indexcache /tmp/luci-indexcache.*.json
rm -rf /tmp/luci-modulecache
printf 'Original navigation restored. Log out and back into LuCI to refresh its menu.\n'
