# ZLT X28: LuCI fix notes

Router: OpenWrt 19.07-SNAPSHOT (mt6890, aarch64), vendor firmware.
Date: 2026-10-20.

## Access

| What | Where |
|---|---|
| SSH | `ssh router` (root, port 2222, key `~/.ssh/router`, `ssh-rsa` enabled in `~/.ssh/config`) |
| LuCI | `http://192.168.70.1:4153/cgi-bin/luci` (no trailing slash) |
| Vendor UI | ports 80 / 443, docroot `/tzwww`, separate from LuCI |

LuCI runs under its own `mini_httpd -p 4153 -d /www`. There is no uhttpd and no `/etc/config/uhttpd`.
The LuCI login is the Linux `root` password (set with `printf 'root:<pw>\n' | ssh router chpasswd`).

## Starting point

- `luci.main.mediaurlbase='/luci-static/bootstrap'` but `/www/luci-static/bootstrap/` and `view/themes/` did not exist, so pages had no theme.
- After login the pages 404'd: only `luci-base.json` existed in `/usr/share/luci/menu.d`, so there was no Status/System menu and no views.
- Source of fixes: `work/luci-review/luci_fixed.tgz`, which comes from https://github.com/EngineerMazeed/ZLT-X28. It is a mixed bag: several files in it are stubs (for example `network.js` is 320 lines vs 4128 on the router), so only files missing on the router were taken. Files that already existed were never overwritten.

## What was changed on the router

All changes are additive unless noted. Everything was `chown root:root`, and `/tmp/luci-indexcache` plus `/tmp/luci-modulecache` were cleared after each deploy.

1. **Bootstrap theme.** Added `/www/luci-static/bootstrap/{cascade.css,mobile.css,favicon.png}`, `/www/luci-static/resources/menu-bootstrap.js`, `/usr/lib/lua/luci/view/themes/bootstrap/{header,footer}.htm`.
2. **Status and System menus and views.** Added `/usr/share/luci/menu.d/luci-mod-status.json`, `luci-mod-system.json`, `/usr/lib/lua/luci/view/admin_status/index.htm`, `/www/luci-static/resources/view/{status,system}/`, CBI icons and SVGs.
3. **Network and firewall pages.** Added `controller/admin/network.lua`, `controller/firewall.lua`, `model/network/proto_*.lua`, `/www/luci-static/resources/view/{network,firewall}/`, `tools/firewall.js`, and the `protocol/*.js` files that were missing. The existing `protocol/{dhcp,none,static}.js` were skipped.
4. **rpcd ACL** `/usr/share/rpcd/acl.d/luci-mod-status.json`: allows `file list` on `/www/luci-static/resources/view/status/include`. Without it the overview spun forever ("Access denied").
5. **ubus stand-in** `/usr/libexec/rpcd/network` + `/usr/share/rpcd/acl.d/luci-mod-network.json`: a read-only script that answers `network get_proto_handlers` from `/lib/netifd/proto/*.sh`. LuCI needs it to know the protocols. Result: Interfaces shows "Quectel MIPC Cellular / DHCPv6 client / Static address" instead of "Unsupported protocol type". Needs an rpcd restart (this logs everyone out).
6. **Removed** `/usr/lib/lua/luci/view/admin_status/index/ddns.htm`. It was copied from the tgz and included a missing template (`ddns/system_status`), which broke the overview template server-side and made the page hang.
7. **Trailing-slash 404.** mini_httpd answers 404 for `/cgi-bin/luci/` (stock uhttpd does not).
   - `/www/index.html`: redirect changed from `cgi-bin/luci/` to `cgi-bin/luci` (original: `/www/index.html.orig`).
   - `/usr/lib/lua/luci/dispatcher.lua`: `build_url()` no longer appends `/` when called with no path, which fixes the post-login and logout redirects (original: `/root/dispatcher.lua.orig`).

## Persistence (added after a reboot)

The router rebooted once and the hand-started servers disappeared, while all deployed LuCI files survived on flash. Both servers now start from `/etc/rc.local` (backup `/root/rc.local.orig`):

- dropbear on `192.168.70.1:2222` (added by you)
- `mini_httpd -p 4153 -h 192.168.70.1 -d /www -c "cgi-bin/*" -u root` for LuCI

Do not run vendor binaries such as `sms_mgr` with unknown flags: `sms_mgr -h` is not a help flag, it ran an AT command against the modem and the router rebooted shortly after.

## Known limits

- **netifd is not running.** The router uses the vendor `ql-netd`; `/sbin/netifd` exists but `/etc/config/network` is stale (LAN `192.168.1.1` on `br-lan`, live LAN is `br0` `192.168.70.1`). Starting netifd or using **Save & Apply on Network pages** could change the LAN address and lock you out. Treat the Network pages as display-only. The interface counters show 0 B and WAN shows down for the same reason.
- Hidden on purpose (stock `depends` rules): Realtime → Wireless, Network → Wireless, Network → Switch (no classic wireless/switch config), System → Mount Points (no `/sbin/block`). WiFi is under the MTK menu.
- Active DHCP Leases shows none (not investigated).
- `GET /ubus/` returns 404 in the console; LuCI falls back to `/admin/ubus`. Harmless.
- Page sweep result: 28 of 32 LuCI pages render; the other 4 are the hidden ones above.
- The login redirect fix has not been tested with a real login from a browser at the time of writing.

## Rollback

```sh
ssh router '
cp /root/dispatcher.lua.orig /usr/lib/lua/luci/dispatcher.lua
cp /www/index.html.orig /www/index.html
rm -f /usr/libexec/rpcd/network /usr/share/rpcd/acl.d/luci-mod-network.json /usr/share/rpcd/acl.d/luci-mod-status.json
rm -rf /usr/share/luci/menu.d/luci-mod-status.json /usr/share/luci/menu.d/luci-mod-system.json
rm -rf /www/luci-static/bootstrap /www/luci-static/resources/view /usr/lib/lua/luci/view/themes /usr/lib/lua/luci/view/admin_status
rm -rf /tmp/luci-indexcache /tmp/luci-modulecache
/etc/init.d/rpcd restart'
```

## Ideas not done

- Compare against `zltx28_luci_stock_full.tgz` from the same GitHub repo for a fuller stock panel.
- Run a real `uhttpd` on a spare port to remove the need for the dispatcher and index.html patches.
- Investigate empty DHCP leases and the slow first load of some pages.
