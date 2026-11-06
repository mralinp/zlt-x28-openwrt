<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo-dark.svg">
  <img src="docs/assets/logo.svg" alt="X28 OpenWrt" width="120">
</picture>

# X28 OpenWrt

**A native OpenWrt 23.05 for the ZLT X28 5G CPE, with WireGuard, OpenVPN, L2TP, PPTP and Passwall2 built in: recovery-first, built in the open, running on a real unit.**

[![Release](https://img.shields.io/github/v/release/mralinp/zlt-x28-openwrt?include_prereleases&label=release)](https://github.com/mralinp/zlt-x28-openwrt/releases)
[![Release workflow](https://github.com/mralinp/zlt-x28-openwrt/actions/workflows/release.yml/badge.svg)](https://github.com/mralinp/zlt-x28-openwrt/actions/workflows/release.yml)
[![CI](https://github.com/mralinp/zlt-x28-openwrt/actions/workflows/ci.yml/badge.svg)](https://github.com/mralinp/zlt-x28-openwrt/actions/workflows/ci.yml)
![SoC](https://img.shields.io/badge/SoC-MediaTek%20MT6890%20(T750)-orange)
![Base](https://img.shields.io/badge/userspace-OpenWrt%2023.05.5-00b5e2)
![Status](https://img.shields.io/badge/status-beta%20%C2%B7%20pre--release-yellow)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue.svg)](LICENSE)

[Status](#status) · [VPN and Passwall2](#vpn-and-passwall2) · [Roadmap](#roadmap-to-a-stable-release) · [How it works](#how-it-works) · [Build](#build-and-flash-overview) · [Changelog](CHANGELOG.md) · [Tests](docs/TESTING.md) · [Docs](docs/README.md) · [Contributing](#contributing)

</div>

> [!WARNING]
> **Your device, your risk.** The X28 is usually someone's only internet connection, and flashing it means
> writing its NAND over the MediaTek download agent. The native image has been flashed to slot A and boots on
> **one tested unit**; the procedure is guarded and owner-approved step by step, and needs a verified backup and a
> UART. It is not a consumer installer. Read [docs/RECOVERY.md](docs/RECOVERY.md) before touching anything.
> Not affiliated with ZLT, Tozed, MediaTek or Quectel.

## Why

The ZLT X28 (MediaTek MT6890/T750, Quectel RG500L modem) ships a locked-down OpenWrt 19.07 with a vendor web
UI. This project puts a **normal OpenWrt** on it: stock LuCI and UCI, netifd, standard DHCP and firewall,
**VPN clients and Passwall2 that work on the vendor kernel**, a cooler box, and local SMS/voice for AI projects, **without losing the ability to recover the unit**. So it goes
recovery first: back up everything, prove a way back, then build and flash.

## Status

Last updated 2026-11-02 (release `v0.37.0`). One unit, one SIM, one carrier.

| Area | State |
|---|---|
| Full NAND backup (51 partitions, hash-verified) | ✅ done |
| USB recovery: preloader + download agent | ✅ all 51 partitions read over USB; `rootfs_a` and `rootfs_sig_a` written and restored with guarded tools |
| Native OpenWrt 23.05.5 on slot A (vendor 4.19.205 kernel, fw3 + iptables-legacy) | ✅ boots; stock slot B untouched |
| 5G data as a normal netifd interface (`x28_mipc`: IPv4, IPv6, IPv4v6, APN from the SIM) | ✅ works, with its own LuCI protocol page |
| LuCI over HTTPS (self-signed, HTTP redirected), LAN bridge (4 sockets), DHCP/DNS, IPv6 on the LAN, firewall and NAT | ✅ works; root has an empty password until you set one |
| WireGuard (our module for the vendor kernel) | ✅ up to 715 Mbit/s sending, CPU not saturated ([below](#vpn-and-passwall2)) |
| OpenVPN client | ✅ about 100 Mbit/s, one CPU core is the limit |
| L2TP and PPTP clients | 🟡 installed, protocols in netifd and LuCI; not yet tested against a server |
| Passwall2 (xray, TPROXY modules we build) | ✅ whole LAN through the node: TCP, UDP and IPv6, switched from LuCI, survives a reboot |
| Wi-Fi (MT7915 dual band, vendor `mt_wifi` through a netifd handler) | 🟡 both radios come up with WPA2 and a phone works through them; throughput tests pending |
| Front panel LEDs (radio, signal, WAN) | ✅ works |
| Everything at boot, settings surviving reboots, SSH key-only on port 22 | ✅ works |
| A/B boot counter | ✅ the preloader adds a try per boot; `x28-bootok` resets it after a good boot, like stock |
| Slot A marked successful | ❌ deliberately not: success stays 0 so the fall-back to stock B remains (see [BOOT-FLOW](docs/BOOT-FLOW.md)) |
| Temperature | ✅ about 40 °C idle on the SoC (stock 65 °C idle without a fan, 46 °C with the 12 V fan) |
| SMS and voice | 🗓️ worked on the stock-firmware overlay (voice blocked by the SIM); not yet on the native image |
| Recovery slot, sysupgrade, fan control, own kernel | 🗓️ planned, see the roadmap |

Every ✅ links to evidence and a reproduce command in **[docs/TESTING.md](docs/TESTING.md)**. The vendor modem
stack is closed-source and not redistributable, so what this repository publishes is the **build tooling and the
packages**, not a ready-to-flash image: the image is assembled locally from your own unit's backup.

## VPN and Passwall2

These were the main reasons to replace the stock firmware. **Every image ships all of them preinstalled, ready to
configure on a clean flash**, before any of your settings: the build refuses to make an image without the WireGuard and TPROXY modules
and `ipset`. Configure them from
stock LuCI pages:

| | How it runs on the vendor 4.19.205 kernel |
|---|---|
| **WireGuard** | The kernel has none. We build `wireguard-linux-compat` against the kernel tree ([`package/x28-kmods`](package/x28-kmods/README.md)) and load it after a good boot, with a crash guard ([#227](https://github.com/mralinp/zlt-x28-openwrt/issues/227)) |
| **OpenVPN** | `openvpn-openssl` and `luci-app-openvpn`, `tun` from the stock kernel |
| **L2TP, PPTP** | `xl2tpd` and `ppp-mod-pptp` as LuCI interfaces |
| **Passwall2** | xray on the iptables path (no nftables here), with TPROXY and socket modules we build, plus a small shim for two symbols the kernel never exported ([PASSWALL2](docs/PASSWALL2.md)) |

![Passwall2 running in LuCI on the X28](docs/images/x28-passwall2-luci.png)

What the X28 can carry with this firmware, measured on the unit on 2026-11-02 ([TESTING 37](docs/TESTING.md#37-vpn-speed-and-cpu-limits-on-the-router-2026-11-02),
[PASSWALL2](docs/PASSWALL2.md#what-the-device-can-carry)). WireGuard and OpenVPN ran `iperf3` between the router and a LAN
peer, so the carrier and the far server are out of the picture:

| Tunnel | Router sends | Router receives | CPU (4 cores) | What limits it |
|---|---|---|---|---|
| None (reference) | 856 Mbit/s | 363 Mbit/s | 9–36% | the test laptop's path |
| WireGuard, 4 streams | 715 Mbit/s | 330 Mbit/s | 55–58% | not reached |
| OpenVPN AES-128-GCM (mbed TLS) | 102 Mbit/s | 58 Mbit/s | 24–27% | one core |
| OpenVPN AES-256-GCM (OpenSSL, the shipped build) | 74 Mbit/s | 84 Mbit/s | 25–27% | one core |
| Passwall2 / xray, LAN client | 40 Mbit/s | 206 Mbit/s measured, about 400 estimated | 56% peak, xray 1.1 cores | the link, not the router |

**Pushing it further** ([details](docs/PASSWALL2.md#pushing-it-further)):

- **WireGuard** for raw speed: it runs in the kernel on all four cores and had headroom at 715 Mbit/s.
- **OpenVPN** is single-threaded at about 100 Mbit/s per tunnel: use UDP and AES-GCM, or split traffic across tunnels.
- **Passwall2** scales with streams and cores: pick a light transport (fewer layers than XHTTP over TLS), keep logs at
  `warn`, and try packet steering, since `cpu0` takes all network interrupts.
- **Heat** is not the limit so far: the SoC idles about 40 °C on this firmware and stayed under 48 °C in these tests.
  A fan or the `performance` CPU governor buys more for sustained loads.

Not yet measured: LAN clients forwarded through each tunnel, L2TP and PPTP against a server, the Passwall2 ceiling
itself, the tuning ideas, and WireGuard over hours.

## Roadmap to a stable release

The target layout is simpler than today's two full firmwares:

- **Slot A: stable OpenWrt**, the thing you run.
- **Slot B: a recovery slot**, a small kernel and recovery path that can rescue the box and install or reinstall
  OpenWrt on slot A, and put the stock firmware back if you want it. This frees the flash that now holds a second
  full firmware and removes the need for the download agent and a UART in everyday recovery.

Steps, roughly in order ([docs/PROJECT-PLAN.md](docs/PROJECT-PLAN.md) has the detail):

1. Soak and test the slot-A image: 48 h without unexplained reboots, Wi-Fi client and throughput tests, more LED
   states, the idle CPU and RAM baseline.
2. Design and build the recovery slot, including the way back to stock.
3. `sysupgrade` for the new layout.
4. A tagged stable release, the device page for the OpenWrt wiki, and build documentation for other owners.
5. Later: fan control from LuCI ([#47](https://github.com/mralinp/zlt-x28-openwrt/issues/47)), local SMS and voice
   on the native image, and a 4.19 kernel plus kmod feed built from a sibling-device SDK
   ([#130](https://github.com/mralinp/zlt-x28-openwrt/issues/130)).

## How it works

```mermaid
flowchart LR
    subgraph CI["GitHub Actions (public)"]
        IB["OpenWrt 23.05.5<br/>ImageBuilder"] --> U["userspace rootfs<br/>fw3 · LuCI · netifd"]
        U --> R["release vX.Y.Z<br/>(pre-release)"]
    end
    subgraph LOCAL["Your machine (private)"]
        B["your unit's backup<br/>(51 partitions)"] --> V["vendor half<br/>4.19 kernel modules<br/>modem and Wi-Fi blobs"]
        R --> S["stage_native.py"]
        V --> S
        S --> F["first_boot.py<br/>x28 packages · policy · ab_guard"]
        F --> P["package_ubi.py<br/>rootfs_a image"]
    end
    P -. "slot_entry.py over USB<br/>(receipts · guards · typed approval)" .-> X28[("ZLT X28<br/>slot A")]
```

- **Open half in CI.** Official 23.05.5 packages, assembled with ImageBuilder. The firewall is fw3 because the
  stock kernel has no `nf_tables`.
- **Vendor half stays local.** The stock kernel modules and vendor binaries are proprietary and specific to a
  firmware build, so they are taken from **your own unit's backup** and never enter this public repo or CI.
- **Our packages** (`package/`): `x28-mipc` (cellular netifd protocol) with its LuCI page, `x28-modem` (starts the
  vendor modem stack), `x28-wifi`, `x28-leds`, `x28-bootok` (A/B boot counter) and `x28-kmods` (WireGuard and TPROXY
  modules for the vendor kernel: sources here, built locally against the kernel tree, loaded after a good boot).
- **Guarded flashing.** The tools in [mralinp/x28-flasher](https://github.com/mralinp/x28-flasher) (`tools/recovery/` there) write only the targets they were built for, check the other
  slot and neighbouring partitions before and after every write, and need a typed phrase from the owner.

## Build and flash overview

Backup, USB and flash steps (1, 2 and 5) run from a checkout of [x28-flasher](https://github.com/mralinp/x28-flasher), which pins this repo as a submodule; the commands below name its `tools/recovery/` paths.

Everything is detailed, with expected output, in [docs/BUILD.md](docs/BUILD.md) and
[docs/TESTING.md](docs/TESTING.md). Hardware: a ZLT X28, a **USB-A-to-USB-C** cable (C-to-C does not work), a **1.8 V**
UART path (a shifter or 1.8 V adapter on the 3-hole footprint: RX, GND, TX from left to right; see
[RECOVERY](docs/RECOVERY.md#uart-debug-console-2-read-side-confirmed)), and a second internet path while the X28 is offline. Tools: Python 3.10+, Docker, `gh`, Homebrew `libusb`
on macOS.

```bash
# 1. Back up and verify every NAND partition (router reachable as `ssh router`)
python3 tools/recovery/dump_partitions.py
python3 tools/recovery/verify_backup.py private/backups/<date>

# 2. Install the pinned mtkclient and read the unit over USB (modem unpowered at start)
/opt/homebrew/bin/python3.14 tools/recovery/setup_mtkclient.py
python3 tools/recovery/read_all.py

# 3. Build the open userspace (Linux x86_64; or take the CI release)
tools/build/userspace.sh out

# 4. Assemble the native image from your backup (details and flags in docs/BUILD.md)
python3 tools/build/stage_native.py   --stock <stock rootfs.tar.gz> --modern <userspace rootfs.tar.gz> ... --output private/build/native-stage-N
docker run --rm -v x28-kbuild:/k -v "$PWD/package/x28-kmods:/src:ro" -v "$PWD/private/kmods:/out" debian:bookworm bash /src/build.sh
gh release download feed-2 -D private/feed-2 -p 'ipset_*' -p 'libipset13_*' -p 'x28-ipset-kernel_*'
python3 tools/build/first_boot.py     --stage private/build/native-stage-N --public-key ~/.ssh/router.pub --stock <stock rootfs.tar.gz> --output private/build/native-management-N --kmods private/kmods --ipk private/feed-2/*.ipk
docker run ... x28-firmware-tools:ubi python3 /tools/build/package_ubi.py --profile /profile --output /out/native-ubi-N

# 5. Flash slot A with the guarded session tool (dry run first; --write needs approval, UART and a second backup copy)
python3 tools/recovery/slot_entry.py rootfs_a write --candidate-dir private/build/native-ubi-N ...
```

The flash step, its gates and the typed approvals are described in
[docs/research/rootfs-a-write-plan.md](docs/research/rootfs-a-write-plan.md) and
[docs/RECOVERY.md](docs/RECOVERY.md). Read both first.

## Documentation

| Doc | What |
|---|---|
| [CHANGELOG.md](CHANGELOG.md) | Milestones and every release |
| [docs/STATUS.md](docs/STATUS.md) | Where the project stands today |
| [docs/TESTING.md](docs/TESTING.md) | **Start here for evidence.** Every test: result, commands, what is not proven |
| [docs/PROJECT-PLAN.md](docs/PROJECT-PLAN.md) | Goal, strategy, phases, roadmap and risks |
| [docs/BUILD.md](docs/BUILD.md) | Building the native image: open half in CI, vendor half locally |
| [docs/RECOVERY.md](docs/RECOVERY.md) | Backup, USB recovery, flash sessions, UART |
| [docs/BOOT-FLOW.md](docs/BOOT-FLOW.md) | A/B slots, the preloader boot counter, the rootfs signature check |
| [docs/NATIVE-CELLULAR.md](docs/NATIVE-CELLULAR.md) | The `x28_mipc` cellular protocol |
| [docs/HARDWARE.md](docs/HARDWARE.md) | CPU, RAM and flash use, the root filesystem tree and the device tree |
| [docs/THERMAL.md](docs/THERMAL.md) | Heat baseline, the 12 V fan, current readings |
| [docs/PASSWALL2.md](docs/PASSWALL2.md) | Passwall2 on TPROXY modules for the vendor kernel, unit state, tunnel speed results |
| [docs/research/kernel-module-crc.md](docs/research/kernel-module-crc.md) | TPROXY module CRCs vs the stock kernel, and how they load anyway |
| [docs/research/vendor-ipset-packaging.md](docs/research/vendor-ipset-packaging.md) | ipset packages for the vendor kernel's module subset |
| [docs/research/signed-package-feed.md](docs/research/signed-package-feed.md) | The signed X28 opkg feed: what's in it, how it's signed and hosted |
| [docs/research/x28-flasher-binary.md](docs/research/x28-flasher-binary.md) | x28-flasher as a single PyInstaller binary: what changes in the guards, identity without git, CI (#272) |
| [docs/research/rust-flasher-design.md](docs/research/rust-flasher-design.md) | Dropped Rust flasher (#270): kept for its protocol and DA findings |
| [docs/research/reset-wps-buttons.md](docs/research/reset-wps-buttons.md) | Reset and WPS button pins, records and boot-time behaviour: no layer wipes flash |
| [docs/FIRMWARE-INVENTORY.md](docs/FIRMWARE-INVENTORY.md) | Kernel, modules, vendor packages, runtime deps |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | Issues, branches, commits, automatic releases |
| [docs/README.md](docs/README.md) | Full documentation tree and code map |

## Releases

Every merge to `main` is released automatically. The version comes from the PR title (Conventional Commits:
`feat` → minor, `type!` → major, otherwise patch); 0.x releases are pre-releases. Assets are the open
userspace rootfs, its package manifest and `SHA256SUMS`. A release alone does not boot the X28 (the vendor half is
added locally); see [docs/BUILD.md](docs/BUILD.md). What changed, release by release: [CHANGELOG.md](CHANGELOG.md).

## Contributing

Issues are the unit of work; every change is a branch (`feature|fix|docs|chore|research/<issue>-slug`) and a
squash-merged PR with a Conventional Commit title. Changes that touch the device need a safety note and a
rollback. Read [docs/WORKFLOW.md](docs/WORKFLOW.md); the project's rules for AI agents are in [CLAUDE.md](CLAUDE.md).
Owners of the same box, or its rebrands (MT6890 + MT7915 + MT7531), are very welcome: compare notes in an issue.

## Credits

[EngineerMazeed/ZLT-X28](https://github.com/EngineerMazeed/ZLT-X28) got LuCI onto the stock firmware.
[mt6890-cpe-recovery](https://github.com/mt6890-cpe-recovery/mt6890-cpe-recovery) published the X28 SP Flash
Tool package with Quectel's download agent. [bkerler/mtkclient](https://github.com/bkerler/mtkclient) does the
USB work. [gaglians/zlt-x28-openwrt2305](https://github.com/gaglians/zlt-x28-openwrt2305) explored 23.05 on the
vendor kernel. OpenWrt and LuCI belong to their projects.

## License

Copyright (C) 2026 Ali Naderi Parizi. The code in this repository is free software under the [GNU GPL v3](LICENSE) (or any later version): anyone may use, modify and redistribute it, but any distributed derivative must be released under the same licence with its complete source, and must keep this copyright notice and credit the original project. OpenWrt, LuCI, mtkclient and vendor components keep their own
licences. Vendor firmware is never distributed here.
