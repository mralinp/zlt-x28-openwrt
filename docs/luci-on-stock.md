# ZLT X28 — a working OpenWrt LuCI panel on the stock firmware

> Root access, key-only SSH, and a repaired LuCI web UI on the ZLT X28 / X28 PRO 5G CPE.
> The vendor firmware keeps running. Nothing in the modem, RIL or network stack is replaced.

```
 vendor UI  ──►  http://192.168.70.1        (ports 80/443, untouched)
 LuCI       ──►  http://192.168.70.1:4153/cgi-bin/luci
 SSH (key)  ──►  ssh -p 2222 root@192.168.70.1
```

This repo documents what we did on one unlocked X28 and ships the small set of files
and patches needed to reproduce it. It builds on
[EngineerMazeed/ZLT-X28](https://github.com/EngineerMazeed/ZLT-X28), which got LuCI
onto the device in the first place. We picked up where that left off: a theme that
rendered, but menus that 404'd, pages that hung, and a Network page that couldn't
name a single protocol.

> **Your device, your risk.** Only do this on a router you own. A wrong file in
> `/usr/lib/lua` can lock you out of the web UI, and a wrong network change can cut
> your only connection. Everything here was done on a live router; every script keeps
> backups. Read the [limitations](#limitations) before pressing *Save & Apply*.

## Contents

- [What you get](#what-you-get)
- [The story, step by step](#the-story-step-by-step)
- [Install](#install)
- [What we changed and why](#what-we-changed-and-why)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)
- [Repo layout](#repo-layout)
- [Credits](#credits)

## What you get

| Area | State |
|---|---|
| Status → Overview, Firewall, Routes, System Log, Kernel Log, Processes, Realtime (Load, Traffic, Connections) | Working |
| System → System, Password, SSH-Keys, SSH Access, Startup, Scheduled Tasks, LEDs, Backup/Flash, Reboot | Working |
| Network → Interfaces | Shows the real protocols (Quectel MIPC Cellular, DHCPv6, Static). **Display only**, see [limitations](#limitations) |
| Network → DHCP and DNS, Hostnames, Static Routes, Diagnostics | Render |
| Network → Firewall (Zones, Port Forwards, Traffic Rules, NAT, Custom Rules) | Render |
| MTK → WiFi, Multi-AP, Web Console | Working (vendor pages, unchanged) |
| Network → Wireless / Switch, Status → Realtime → Wireless, System → Mount Points | Hidden on purpose, because their stock prerequisites do not exist on this firmware |

Plus: SSH on port 2222 with key authentication only, and root login to LuCI.

## The story, step by step

1. **An unlocked X28.** A ZLT X28 CPE with the vendor firmware: OpenWrt 19.07 base,
   kernel 4.19, MediaTek MT6890, aarch64, Quectel modem. The vendor web UI runs on
   ports 80/443 (`mini_httpd`, document root `/tzwww`).
2. **A foothold.** Telnet access