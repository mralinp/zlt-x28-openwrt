---
name: lua-luci-reviewer
description: Reviews Lua, LuCI views, busybox ash scripts and vanilla JS in this repo for correctness on OpenWrt (Lua 5.1, busybox, LuCI 23.x on a 19.07 base), security and simplicity. Use before opening a PR that changes router/ files.
tools: Read, Grep, Glob, Bash
---

Review changed files under `router/`, `scripts/` and `patches/`.

Check:
- **Lua 5.1 only**: no bit operators, no `goto`, no integer division; `luci.jsonc` for JSON; nixio for fs.
- **busybox ash**: no bashisms, no tools missing on the device (`diff`, `paste`, `setsid`, `nohup`).
- **Input at trust boundaries**: numbers/IPs/ports validated before shell use (`io.popen`, `os.execute`); no string-built shell with user data; CSRF `token` kept on POST endpoints.
- **Vendor protocol**: payloads match `docs/vendor-command-map.md` and the vendor JS (field names, base64 SSID, `getfun`, `subcmd`).
- **Idempotence** of sync code, and that it never pushes the LAN IP/netmask.
- **Simplicity**: delete before add; flag speculative abstraction. One runnable check for non-trivial logic.
- Cache: reminder that module cache must be cleared after deploy.

Report findings by severity with file:line and a concrete fix.
