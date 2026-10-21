# ZLT X28 OpenWrt

> A modern, optimized, fully working OpenWrt for the **ZLT X28 / X28 PRO 5G CPE**
> (MediaTek MT6890 / T750, 4x Cortex-A55), plus local **SMS and voice** control for AI projects,
> with no operator gateway in the middle.

```
 today     vendor firmware (OpenWrt 19.07, kernel 4.19) + our LuCI, bridge and adapter on top
 next      stock LuCI options that really change the router (UCI <-> vendor backend adapter)
 then      real netifd / fw4 / dnsmasq, vendor daemons retired one by one
 goal      our own OpenWrt image on the vendor kernel and modem blobs, flashed to the inactive A/B slot
```

> **Your device, your risk.** This project touches a live router that is also your internet connection.
> Everything here assumes a unit you own, a full flash backup, and a way back to stock. Read
> [docs/PROJECT-PLAN.md](docs/PROJECT-PLAN.md) (Phase 0) before flashing anything. Not affiliated with ZLT, Tozed, MediaTek or Quectel.

## Status

| Area | State |
|---|---|
| Root SSH (key-only, port 2222) and LuCI on `:4153` | Working, persistent across reboots |
| Vendor bridge (LuCI -> `http.cgi`, logs in with `/etc/vendor-ui.cred`) | Working |
| Vendor menu in LuCI: LAN/DHCP, WiFi, Port forwarding, DMZ, SMS, USSD, Voice | Working (loading verified; saves not all exercised) |
| SMS send / receive | Working |
| Voice calls | Blocked: SIM has no VoLTE/IMS registration and no CS fallback on this network |
| Stock LuCI Network/Firewall pages changing the router | In progress: `vendorsync` adapter (DHCP/DNS, port forwards, DMZ) |
| Full NAND backup (51 partitions, hash-verified) | Done, see [docs/RECOVERY.md](docs/RECOVERY.md) |
| USB recovery (MediaTek preloader + download agent) | Port and security state confirmed; USB flash read not working yet |
| Custom firmware image | Planned (A/B slot, needs proven USB restore + UART first) |

## Architecture

```
 browser ──► LuCI (mini_httpd :4153)
              ├─ stock pages ──► UCI (/etc/config) ──► vendorsync ──┐
              └─ Vendor pages ───────────────────────────────────────┤
                                                                     ▼
                                              vendorbridge ──► /tzwww/cgi-bin/http.cgi ──► vendor daemons
                                                                                       (ql_netd, firewalltools,
                                                                                        lan_mgr, sms_mgr, ril)
 voicectl ──► sample_voice (libqlvoice) ──► modem
```

## Repository layout

| Path | What |
|---|---|
| `router/` | Overlay files copied to the router (`usr/`, `etc/`, `www/`): bridge, controller, views, adapter, init scripts |
| `scripts/` | `install.sh` (deploy LuCI fixes), helpers |
| `tools/recovery/` | Backup, verify and USB recovery scripts, one per step ([docs/RECOVERY.md](docs/RECOVERY.md)) |
| `patches/` | Patches against stock files (`dispatcher.lua`) |
| `docs/` | [Recovery](docs/RECOVERY.md), [project plan](docs/PROJECT-PLAN.md), [workflow](docs/WORKFLOW.md), [vendor command map](docs/vendor-command-map.md), [LuCI on stock firmware](docs/luci-on-stock.md), [fix notes](docs/luci-fix-notes.md) |
| `.claude/agents/` | Project agents for Claude Code (planner, safety auditor, reviewer, researcher) |
| `CLAUDE.md` | Rules and context for Claude Code sessions |

Not in the repo on purpose: the vendor web UI (`vendor-ui/`), firmware dumps and USB probe logs
(kept in the git-ignored `private/`), SSH keys, credentials.

## Quick start (existing unit with root SSH)

```sh
ssh -p 2222 root@192.168.70.1                      # key auth only
# LuCI: http://192.168.70.1:4153/cgi-bin/luci      (no trailing slash)
```

Deploy files from this repo (never use plain `tar` on macOS; it adds `._*` files and your uid):

```sh
cd router && COPYFILE_DISABLE=1 tar --uid 0 --gid 0 -cf - usr etc | ssh router 'cd / && tar xf -'
ssh router 'rm -rf /tmp/luci-modulecache /tmp/luci-indexcache'
```

The bridge needs the vendor login in `/etc/vendor-ui.cred` on the router (line 1 user, line 2 password, mode 600).
Change the default passwords before exposing anything.

## Roadmap

Seven phases, from safety (flash dump, UART) to a released image. See [docs/PROJECT-PLAN.md](docs/PROJECT-PLAN.md).
Work is tracked as GitHub issues with priority and area labels and milestones per phase.

## Contributing

Issues are the unit of work; every change is a branch and a pull request. Read [docs/WORKFLOW.md](docs/WORKFLOW.md):
GitFlow, with **no `develop` branch until the first release**. Hardware-touching changes need a safety note in the PR.

## Credits

Builds on [EngineerMazeed/ZLT-X28](https://github.com/EngineerMazeed/ZLT-X28), which got LuCI onto the device.
LuCI and OpenWrt belong to their respective projects.

## License

MIT for the code in this repository (see [LICENSE](LICENSE)). OpenWrt, LuCI and vendor components keep their own licenses.
