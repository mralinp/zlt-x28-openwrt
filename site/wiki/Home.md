# X28 OpenWrt wiki

OpenWrt 23.05.5 for the **ZLT X28 and X28 PRO** 5G routers (MediaTek MT6890 / T750, 4x Cortex-A55, vendor kernel 4.19.205,
aarch64 musl). A native OpenWrt userspace replaces the stock interface; the vendor kernel and the closed modem stack stay as the
hardware backend.

This wiki is the short version of everything in [`docs/`](https://github.com/mralinp/zlt-x28-openwrt/tree/main/docs). Each page
says what you need to know and links to the full document with the evidence. When the wiki and a document disagree, the document
(and [TESTING](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/TESTING.md)) wins.

**Current release:** v1.2.2 (stable, 2026-11-15). Wiki written 2026-11-14, last edited 2026-11-16.

## Pages

| If you want to... | Read |
|---|---|
| Install it, log in, upgrade, reset | [Getting started](Getting-Started.md) |
| Understand how the image is put together | [Architecture](Architecture.md) |
| Know the board: SoC, flash, Wi-Fi, switch, USB, UART, heat | [Hardware](Hardware.md) |
| See every package we wrote and what it does | [Packages](Packages.md) |
| Use `opkg`, kernel modules, WireGuard | [Package feed](Package-Feed.md) |
| Configure 5G, bands, operator, SMS and the HTTP API | [Cellular and telephony](Cellular-and-Telephony.md) |
| Run WireGuard, OpenVPN or Passwall2 | [VPN and Passwall2](VPN-and-Passwall2.md) |
| Understand A/B slots, the boot counter, sysupgrade and signing | [Boot, slots and upgrades](Boot-Slots-and-Upgrades.md) |
| Back up, recover a unit, or touch flash | [Recovery and safety](Recovery-and-Safety.md) |
| Build an image or cut a release | [Build and release](Build-and-Release.md) |
| Contribute: issues, branches, PRs, local checks | [Development](Development.md) |
| Check what was actually proven | [Test log](Test-Log.md) |
| Read what we tried, measured and dropped | [Experiments and research](Experiments-and-Research.md) |
| See how it got here | [History](History.md) |

## What works

| Area | State |
|---|---|
| Web and shell | Standard LuCI over HTTPS, UCI, SSH on port 22 (LAN only) |
| Cellular | 5G/LTE data through our `x28_mipc` netifd protocol: IPv4, IPv6, APN from the SIM, operator scan and selection, 4G/5G band lock, LTE cell lock, roaming switch, signal status |
| Text messages | LuCI pages, a phone book and an HTTP API with keys (since v1.1.0) |
| LAN | Four sockets bridged (one is 2.5 G), `dnsmasq` DHCP/DNS, IPv6, fw3 firewall and NAT |
| Wi-Fi | MT7915 dual band on the vendor `mt_wifi` driver, WPA2, WPS button |
| VPN and proxy | WireGuard, OpenVPN, Passwall2 (TPROXY) preinstalled |
| Updates | Signed A/B `sysupgrade` (CLI and LuCI button), signed `opkg` feed with modules built for this kernel |
| Hardware | Front LEDs, boot counter reset, factory reset from the button (10 s hold) and LuCI; about 40 °C idle |

## What does not (yet)

- **Voice calls with audio.** In experiments IMS registers and calls connect in both directions, but the modem sets up no voice bearer, so there is no sound and the network ends the call after about 20 s. Nothing is shipped ([Cellular and telephony](Cellular-and-Telephony.md#voice-calls-connect-but-no-audio)).
- **nftables / firewall4, namespaces, Bluetooth, mac80211.** The vendor kernel lacks them; 578 of the 976 official `kmod-*` packages stay refused.
- **USB host.** The port supplies no 5 V; bus-powered devices are not detected.
- **Fan control.** The board has no fan header.
- **A recovery slot.** Recovery is the flasher over USB download mode; it needs a computer.
- **A newer kernel.** Researched, not attempted ([Experiments](Experiments-and-Research.md)).

Tested on one X28 and one X28 PRO, one carrier. Most feature tests ran on the X28. Details and the unproven list:
[Test log](Test-Log.md).

## Repositories

| Repo | What |
|---|---|
| [mralinp/zlt-x28-openwrt](https://github.com/mralinp/zlt-x28-openwrt) | packages, build tools, docs, releases, the signed feed |
| [mralinp/x28-flasher](https://github.com/mralinp/x28-flasher) | guided backup, image assembly, flashing and recovery. The only supported way to install |
| `mralinp/x28-vendor-inputs` (private) | the stock rootfs CI builds the image from. Vendor files never enter the public repo |

License: GPL-3.0-or-later. Not affiliated with ZLT, Tozed, MediaTek or Quectel.
