# CLAUDE.md: ZLT X28 OpenWrt

Project: an optimized, modern OpenWrt for the ZLT X28 5G CPE (MediaTek MT6890, 4x Cortex-A55, kernel 4.19.205, aarch64 musl),
with working stock LuCI, cooler operation, and local SMS/voice for AI projects. Read `README.md`, `docs/STATUS.md` and
`docs/PROJECT-PLAN.md` first. The native image (OpenWrt 23.05.5) runs on slot A of the test unit; the roadmap is a stable slot A
plus a recovery slot on B. History: `CHANGELOG.md`.

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
- Native image flashing goes only through the guarded sessions in `tools/recovery/` (dry run first; typed phrase from the owner for each step;
  never edit those tools mid-chain: their hashes bind the receipts). The router-safety-auditor reviews any change to them.
- The preloader adds a boot "try" to the A record on boots; `x28-bootok` resets it. Do not reboot the unit casually while it is not reset,
  and never boot stock B with A's tries above 3 (B repairs, i.e. erases, A).
- `misc` is not writable over the download agent (block writes were never acknowledged). It is changed only live, with the stock `dd-nand` byte method, after a full dump, one copy at a time, with the whole partition compared after each write.
- Heat matters: SoC idles ~65 C, no fan. Avoid long-running heavy jobs on the device.

## Deploying to the router (stock-firmware overlay only; the native image is built and flashed, see `docs/BUILD.md`)
- macOS tar pollutes the router with `._*` files and uid 501. Always:
  `cd router && COPYFILE_DISABLE=1 tar --uid 0 --gid 0 -cf - usr etc | ssh router 'cd / && tar xf -'`
- After Lua/LuCI changes: `ssh router 'rm -rf /tmp/luci-modulecache /tmp/luci-indexcache'` (module cache otherwise serves old code).
- Router shell is busybox ash: no `diff`, `paste`, `setsid`, `nohup`, `scp` (no sftp). Use `ssh router 'cat > f' < local`.
- Access: SSH key auth, `ssh router` (port 22 on the native image, 2222 on older ones; `~/.ssh/config`); LuCI `http://192.168.70.1/cgi-bin/luci` (empty root password until you set one); the native image has no vendor UI.

## Architecture in one paragraph
**Native image (current):** OpenWrt 23.05.5 userspace on the vendor 4.19.205 kernel, built by `tools/build/` (`stage_native.py` -> `first_boot.py` -> `package_ubi.py`)
and flashed to slot A by `tools/recovery/slot_entry.py`. Vendor daemons (`ql_ril_service`, `ql_netd`, `mipc_submonitor`, `atci_service`, ...) run only as the modem
backend, started by `package/x28-modem`; networking is standard OpenWrt (netifd, dnsmasq, fw3) with our `x28_mipc` protocol for the 5G WAN, `x28-wifi` for the
MT7915, `x28-leds` for the front LEDs and `x28-bootok` for the A/B boot counter. Details: `docs/STATUS.md`, `docs/BUILD.md`, `docs/NATIVE-CELLULAR.md`.
**Stock-firmware overlay (legacy):** `router/usr/lib/lua/vendorbridge.lua` logs into `/tzwww/cgi-bin/http.cgi` (creds in `/etc/vendor-ui.cred`, session cached in
`/tmp/vendor.sess`) and proxies JSON commands (`docs/vendor-command-map.md`); `vendorsync` maps UCI to vendor commands; `voicectl` drives `sample_voice` through a FIFO.
LuCI quirks there: cookie `sysauth` with stale duplicates, mini_httpd 404s on a trailing slash.

## Conventions
- Shell: POSIX/busybox ash. Lua 5.1 (no bit ops; no `//`). JS: no build step, vanilla.
- Keep it small: no abstractions without a second user, no config for constants. Comment only non-obvious "why".
- Anything non-trivial leaves one runnable check (e.g. `vendorsync selftest`).
- Do not commit: SSH keys, credentials, `vendor-ui/`, firmware dumps, scratch scripts that embed logins (see `.gitignore`).

## Agents (`.claude/agents/`)
`issue-planner` (turn goals into labeled issues), `router-safety-auditor` (review any change that touches the device),
`lua-luci-reviewer` (code review for Lua/LuCI/ash), `firmware-researcher` (read-only recon, never writes to the device).
Use the safety auditor before any `risk/*` PR.
