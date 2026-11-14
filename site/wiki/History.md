# History

Short timeline. The full record is [CHANGELOG.md](https://github.com/mralinp/zlt-x28-openwrt/blob/main/CHANGELOG.md).

| When (2026) | Versions | What happened |
|---|---|---|
| 10-20 | – | Device audit on stock firmware (OEM 1.5.13, OpenWrt 19.07-derived). SoC idles at 65 °C. Project plan written |
| 10-20 → 10-23 | v0.1.0 | **Foundation.** Verified backup of all 51 partitions, USB recovery through the download agent, firmware inventory, CI build of the 23.05.5 userspace, QEMU boot test, automatic releases |
| 10-23 → 10-29 | v0.1.5 – v0.12 | **Recovery and boot-flow research.** UART console, the A/B slot map, the rootfs signature traced in LK, first identical-byte and changed-page USB writes |
| 10-28 → 10-29 | v0.12 – v0.22 | **Native image on slot A.** Guarded flash sessions, LAN, DHCP, IPv6, the `x28_mipc` protocol, Wi-Fi, LEDs, everything at boot, `x28-bootok`. First 5G data on native OpenWrt on 10-29 |
| 10-31 → 11-02 | v0.30 – v0.38 | **VPNs and Passwall2.** WireGuard, OpenVPN, TPROXY modules built for the kernel, the first signed feed, the LAN kill switch, speed measurements |
| 11-03 → 11-06 | v0.39 – v0.57 | **Carrier control and the flasher.** WPS, operator selection, band and cell lock, the Carrier tab. The flasher became a single binary and moved to its own repo. Second unit (X28 PRO). Relicensed MIT → GPL-3.0-or-later |
| 11-07 → 11-08 | v0.57.3 – v0.68.0 | **One set of packages.** `feed-3` with 28 built module packages, `x28-kmods` loader, the `x28-*` packages and `x28-base`, the assembly bundle |
| 11-08 → 11-09 | v0.68.1 – v0.78.0 | **Sysupgrade.** A/B upgrade to the other slot, signed images, the image built in CI, the update notice and `x28-upgrade` |
| 11-10 | **v1.0.0** | **First stable release.** `develop` for pre-releases, `main` for stable |
| 11-13 | v1.1.0, v1.1.1 | Text messages with a phone book and HTTP API, factory reset from the button and LuCI, the landing page, an IPv4 passthrough experiment |

## Strategy, as it changed

| Stage | Plan | Outcome |
|---|---|---|
| 1 | Adapter layer on stock firmware | built, then superseded |
| 2 | Take over networking with netifd, fw3, dnsmasq | done |
| 3 | Rebuilt rootfs on the vendor kernel | done, boots on two units |
| 4 | Stable release | v1.0.0 |

Decisions that shaped it:

- **Stay on the vendor kernel.** Modem and Wi-Fi blobs are tied to it.
- **fw3, not fw4.** The kernel has no `nf_tables`.
- **No recovery slot.** The preloader's fall-back to the other slot is worth more than 64 MiB.
- **Publish the image.** Since v0.75.0 CI builds the full image from private inputs; the inputs stay private.
- **Refuse, do not pretend.** `opkg` refuses a kernel module that cannot load instead of installing it.

## Next

- Finish `sysupgrade`: keeping settings verified, LuCI's flash page, the hardware pass with interrupted writes.
- A full 48 h soak; Wi-Fi client and throughput tests.
- Voice calls: calls already connect in experiments; the audio path is the open problem. An OpenWrt wiki device page. Later, an own 4.19 kernel from the SDK.

See [ROADMAP](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/ROADMAP.md) and the
[open issues](https://github.com/mralinp/zlt-x28-openwrt/issues).

## Credits

Built on OpenWrt and LuCI, with work from [EngineerMazeed](https://github.com/EngineerMazeed/ZLT-X28),
[mt6890-cpe-recovery](https://github.com/mt6890-cpe-recovery/mt6890-cpe-recovery),
[mtkclient](https://github.com/bkerler/mtkclient) and [gaglians](https://github.com/gaglians/zlt-x28-openwrt2305).
