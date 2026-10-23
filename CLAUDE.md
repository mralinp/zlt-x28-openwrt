# CLAUDE.md: ZLT X28 OpenWrt

Project: an optimized, modern OpenWrt for the ZLT X28 5G CPE (MediaTek MT6890, 4x Cortex-A55, kernel 4.19.205, aarch64 musl),
with working stock LuCI, cooler operation, and local SMS/voice for AI projects. Read `README.md` and `docs/PROJECT-PLAN.md` first.

## Workflow (non-negotiable)
- **Everything is an issue.** No issue, no branch. Use labels: one priority (`P0`-`P3`), one `type/*`, one or more `area/*`, `risk/*` when relevant, and a phase milestone.
- **Trunk-based: only `main`; every merge to `main` is a release.** Work on `feature|fix|chore|docs|research/<issue>-slug` branched from `main`; open a PR into `main`; squash-merge. Never push to `main` directly (the initial commit is the only exception).
- `release.yml` tags `vX.Y.Z` and publishes a GitHub release automatically (0.x = pre-release, first is v0.1.0). The **PR title** decides the bump (`feat` minor, `type!`/`BREAKING CHANGE` major (minor on 0.x), else patch), so it must be a Conventional Commit; CI checks it.
- Conventional Commits (`feat(adapter): ...`), issue referenced in the body. End commits with the attribution line the session provides.
- PRs follow `.github/PULL_REQUEST_TEMPLATE.md`: what/why, `Closes #n`, test evidence from a real unit, safety note + rollback for `risk/*`, and an explicit "not verified" list.
- Never merge, force-push, create or delete repos/branches on the remote, or change repo settings without the user's explicit OK.

## Hardware safety rules (learned the hard way)
- The router is the user's internet connection. One change per step. Back up the file/config first and check the backup is non-empty.
- Read-only recon by default (`ssh router '...'`, GET calls through the bridge). Ask before anything that writes to flash, changes network/LAN/WAN, the modem mode, passwords, or reboots.
- Never run vendor binaries with unknown flags (`sms_mgr -h` rebooted the device). Never put the LAN IP/netmask behind an automatic apply path.
- Never enter passwords, forge sessions (`ubus session create`), or run broad `find / -exec rm|chown` on the router. Sending an SMS or placing a call needs the user to name the number.
- Flash/bootloader work (`risk/brick`) requires: full verified mtd dump, UART access, tested way back, and only the inactive A/B slot.
- Heat matters: SoC idles ~65 C, no fan. Avoid long-running heavy jobs on the device.

## Deploying to the router
- macOS tar pollutes the router with `._*` files and uid 501. Always:
  `cd router && COPYFILE_DISABLE=1 tar --uid 0 --gid 0 -cf - usr etc | ssh router 'cd / && tar xf -'`
- After Lua/LuCI changes: `ssh router 'rm -rf /tmp/luci-modulecache /tmp/luci-indexcache'` (module cache otherwise serves old code).
- Router shell is busybox ash: no `diff`, `paste`, `setsid`, `nohup`, `scp` (no sftp). Use `ssh router 'cat > f' < local`.
- Access: SSH key auth, `ssh router` (port 2222, `~/.ssh/config`); LuCI `http://192.168.70.1:4153/cgi-bin/luci` (no trailing slash); vendor UI on ports 80/443.

## Architecture in one paragraph
Vendor daemons (`ql_netd`, `firewalltools`, `lan_mgr`, `sms_mgr`, `ql_ril_service`) own the real state. `router/usr/lib/lua/vendorbridge.lua`
logs into `/tzwww/cgi-bin/http.cgi` (creds in `/etc/vendor-ui.cred`, session cached in `/tmp/vendor.sess`) and proxies JSON commands;
the full command list is in `docs/vendor-command-map.md`. LuCI pages under Vendor use it; `vendorsync` maps UCI (dhcp, firewall redirects, DMZ) to vendor commands and back.
`voicectl` drives `sample_voice` through a FIFO. LuCI quirks: cookie `sysauth` with stale duplicates (dispatcher tries all), mini_httpd 404s on a trailing slash.

## Conventions
- Shell: POSIX/busybox ash. Lua 5.1 (no bit ops; no `//`). JS: no build step, vanilla.
- Keep it small: no abstractions without a second user, no config for constants. Comment only non-obvious "why".
- Anything non-trivial leaves one runnable check (e.g. `vendorsync selftest`).
- Do not commit: SSH keys, credentials, `vendor-ui/`, firmware dumps, scratch scripts that embed logins (see `.gitignore`).

## Agents (`.claude/agents/`)
`issue-planner` (turn goals into labeled issues), `router-safety-auditor` (review any change that touches the device),
`lua-luci-reviewer` (code review for Lua/LuCI/ash), `firmware-researcher` (read-only recon, never writes to the device).
Use the safety auditor before any `risk/*` PR.
