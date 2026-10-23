# Read-only modem preview

Open: http://192.168.70.1:4153/cgi-bin/luci/admin/status/x28_native

Under **Status → Native OpenWrt preview**. Covers interfaces, LAN/DHCP, cellular, wireless, firewall/NAT, routing/DNS, VPN/proxy and system/services.

Live snapshots read interface addresses, device MTU/state, bridge members, resolver addresses, lease count, kernel routes, iptables table names, connection counts, selected process names, memory and mounts. Capability checks report file/module presence only. No secrets, Wi-Fi keys or VPN credentials are read. No OEM CGI, shell commands, modem activation or network service mutations are used.

Proposed settings are explicitly labelled examples. All preview fields are in disabled fieldsets, Save and Apply are disabled, no form submits, and the authenticated controller rejects non-GET requests with 405. The rest of the existing LuCI administration interface retains its usual functionality; this restriction applies to the preview page.

The page is a visual preview, not the native protocol form executing under netifd. The native prototype remains uninstalled. No firmware image has been built.

## Verification

`python3 test_readonly.py` checks section coverage, disabled fields/buttons, escaped live output and absence of controller mutation calls. `python3 test_readonly.py --live` prompts for the current root LuCI password and checks authenticated rendering and POST rejection. Both checks passed on 2026-10-21. The existing default route and vendor WAN manager remained active.

## Rollback

The previous preview files were copied to `/root/x28-preview-backup-20261021/`. Restore `x28_preview.lua` to `/usr/lib/lua/luci/controller/` and `native_preview.htm` to `/usr/lib/lua/luci/view/x28/`, then remove the cached preview controller `/tmp/luci-modulecache/6C7563692E636F6E74726F6C6C65722E7832385F70726576696577` and `/tmp/luci-indexcache`. No network service restart is needed.
