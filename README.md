<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo-dark.svg">
  <img src="docs/assets/logo.svg" alt="X28 OpenWrt" width="120">
</picture>

# X28 OpenWrt

**OpenWrt 23.05.5 for the ZLT X28 and X28 PRO 5G routers.**

[![Release](https://img.shields.io/github/v/release/mralinp/zlt-x28-openwrt?include_prereleases&label=release)](https://github.com/mralinp/zlt-x28-openwrt/releases)
[![Downloads](https://img.shields.io/github/downloads/mralinp/zlt-x28-openwrt/total)](https://github.com/mralinp/zlt-x28-openwrt/releases)
[![CI](https://github.com/mralinp/zlt-x28-openwrt/actions/workflows/ci.yml/badge.svg)](https://github.com/mralinp/zlt-x28-openwrt/actions/workflows/ci.yml)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue.svg)](LICENSE)

[Get started](#get-started) · [Documentation](docs/README.md) · [Contributing](#contributing) · [Releases](https://github.com/mralinp/zlt-x28-openwrt/releases)

</div>

## What works

Tested on **X28 and X28 PRO**. A native OpenWrt userspace replaces the stock interface while keeping the vendor kernel and modem backend.

| Feature | Included |
|---|---|
| Web interface | Standard LuCI over HTTPS, UCI configuration and SSH |
| Cellular | 5G data, APN settings, operator selection, band/cell locking and signal status in LuCI |
| Networking | Dual-band Wi-Fi, LAN, DHCP/DNS, firewall, NAT and IPv6 on LAN |
| VPN and proxy | WireGuard, OpenVPN and Passwall2 preinstalled |
| Updates | Working signed firmware upgrades and a signed, kernel-compatible `opkg` package feed |
| Hardware | Front-panel LEDs and boot-counter management; about 40 °C idle SoC temperature on the test unit |

This is community firmware using the vendor 4.19.205 kernel, not an official OpenWrt device image. Most feature testing was on the X28; not every feature has been verified on both models. SMS and voice are not supported yet. See [status and limitations](docs/STATUS.md) and [test evidence](docs/TESTING.md).

## LuCI and Passwall2

Configure networking through standard LuCI pages and manage Passwall2 from its web interface. The screenshot below shows Passwall2 running on the X28, with connectivity checks through the configured node.

![Passwall2 running in LuCI on the X28, with successful connectivity checks](docs/images/x28-passwall2-luci.png)

See the [VPN setup notes and measured performance](docs/PASSWALL2.md).

## Get started

Use **[x28-flasher](https://github.com/mralinp/x28-flasher)** for installation, backup and recovery—the only supported installation path.

1. Get the flasher and follow its setup instructions. If it is not public yet, wait for its release; do not flash manually.
2. Connect your router with a **USB-A to USB-C** cable (USB-C to USB-C does not work).
3. Follow the flasher's guided steps: connect, make a verified full backup, enable root access, prepare the image, flash OpenWrt and select the boot slot. Keep a second copy of your backup offline.
4. After boot, open **https://192.168.70.1/cgi-bin/luci**, accept the self-signed certificate and set a root password. SSH is available on port 22 from the LAN.

![X28 Flasher application for guided backup and installation](docs/images/x28-flasher.png)

> [!WARNING]
> Flashing can brick your router. Use the flasher's safety checks; never write partitions or change the boot order by hand. Read the [recovery guide](docs/RECOVERY.md) first. Firmware upgrades write the inactive slot, so the first upgrade can replace the stock firmware fallback. Back up your settings before upgrading.

> [!NOTE]
> **Carrier unlocking:** we will provide step-by-step instructions later.

## Updates and packages

- **Firmware:** signed A/B upgrades write and verify the inactive slot before switching to it. Download the signed `x28-sysupgrade-<version>.tar` from [releases](https://github.com/mralinp/zlt-x28-openwrt/releases). The CLI and LuCI update controls are available in recent images; nothing installs automatically. Back up your configuration first—settings preservation is not fully verified.
- **Packages:** use LuCI's **System → Software** or `opkg`. The image includes our signed feed for packages compatible with the vendor kernel; incompatible kernel modules are refused rather than installed.

See [firmware upgrade details](docs/research/sysupgrade-design.md) and the [package-feed guide](docs/PACKAGE-FEED.md) for compatibility, safety and known limits.

## Contributing

Bug reports, test results and pull requests are welcome.

1. [Open an issue](https://github.com/mralinp/zlt-x28-openwrt/issues) before starting work. Include your model, firmware version and relevant logs; remove credentials and device identifiers.
2. Branch from `develop` as `feature|fix|docs|chore|research/<issue>-slug`.
3. Submit a PR into `develop` with a Conventional Commit title and a reference to the issue. Include test results, anything not verified, and a safety/rollback note for changes that affect the device.

See the [contribution workflow](docs/WORKFLOW.md) for labels, milestones and review requirements.

## Documentation

The **[documentation index](docs/README.md)** covers installation, recovery, firmware upgrades, packages, hardware and development. See the [changelog](CHANGELOG.md) for release history.

## Credits and license

Built on OpenWrt and LuCI, with work from [EngineerMazeed](https://github.com/EngineerMazeed/ZLT-X28), [mt6890-cpe-recovery](https://github.com/mt6890-cpe-recovery/mt6890-cpe-recovery), [mtkclient](https://github.com/bkerler/mtkclient) and [gaglians](https://github.com/gaglians/zlt-x28-openwrt2305).

Copyright (C) 2026 Ali Naderi Parizi. Repository code is [GPL-3.0-or-later](LICENSE); third-party components retain their own licenses. Not affiliated with ZLT, Tozed, MediaTek or Quectel.
