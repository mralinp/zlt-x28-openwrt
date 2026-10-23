# Unfinished stock LuCI preview

Status on 2026-10-21: NOT WORKING. The proposed CGI reuses stock LuCI view modules, sets read-only page metadata and provides an explicit read RPC allowlist. A UI guard supplements backend rejection; it is not a security boundary.

Twenty denial cases passed in a direct Lua test on the router. These tests do not establish HTTP security or browser correctness. HTTP testing failed before any genuine page was successfully rendered.

A temporary procd service named `x28-stock-preview` was started on LAN port 4154 using `/tmp/x28-stock-luci/www`. It has no persistent boot init script. The temporary service was stopped during repository migration; port 4154 is not intended to remain listening. The last deployed CGI returned an error because `luci.config` was not explicitly required. The source here adds explicit imports for config/template/jsonc; that repair has NOT been deployed or tested. Automatic approval review could not complete because of a usage limit at the last attempt. No native modem protocol was activated.

Next steps: repair or stop that temporary instance, test authentication and all disallowed RPC paths over HTTP, then verify genuine Interfaces/Wireless/DHCP/Firewall pages in a browser. Audit assumptions in wireless profile mapping and synthetic runtime status. Do not present these observations as netifd ownership.

`test_http.py` prompts for the existing password. It is an integration test containing denied write/command requests and should only target this isolated gateway after checking the deny policy. `test.lua` mocks forwarding and verifies 20 denied operations. No firmware image is built here.
