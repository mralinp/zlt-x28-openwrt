# ZLT X28 community firmware project — research brief

Scope update, 2026-10-21: the primary deliverable is now the native OpenWrt port in [PROJECT-PLAN.md](PROJECT-PLAN.md). OEM UI wrappers are historical tools and are excluded from that firmware image.

**Status:** Research and planning. No public custom firmware image or verified installation procedure yet. Tested device: ZLT X28, OEM firmware 1.5.13, MT6890/T750 target `evb6890v1_64_cpe_nand`, Linux 4.19.205, OpenWrt 19.07-derived userspace. These observations describe one unit and may differ across revisions.

## Goal

Make the X28 a capable, independently maintainable 5G OpenWrt router so owners can use LuCI, WireGuard/OpenVPN, and advanced routing without a second box. The first deliverables will be open build/configuration work and safe documentation. A flashable release needs working 5G, Wi-Fi, Ethernet, SIM configuration, recovery, and licensing checks.

## What already exists

- [Experimental 23.05 X28 port](https://github.com/gaglians/zlt-x28-openwrt2305): a valuable bring-up reference. It needs proprietary T750 SDK components and reuses the vendor 4.19 kernel; it is not a self-contained or supported image.
- [X28 USB recovery project](https://github.com/safuapy/zlt-x28-unbrick): proposes patched `mtkclient`, a Quectel download agent, and stock images. Its code, binary provenance, and procedure need independent audit and testing on a spare unit before use.
- [Mainline MT7915 Wi-Fi support](https://wireless.docs.kernel.org/en/latest/en/users/drivers/mediatek.html) exists in `mt76`; that is promising for a future maintained-kernel port. Cellular CCCI/MIPC integration and MT6890 board support remain unresolved.

## Release milestones

1. **Public-safe hardware dossier:** compare board revisions, partition tables, boot logs, Wi-Fi/modem topology, and kernel config. No unique identifiers, keys, credentials, or calibration dumps.
2. **Proven recovery:** review the USB recovery toolkit and establish serial/bootloader access. A second device or fallback internet connection is needed for flash experiments.
3. **OEM-based enhancement package:** reproducible configuration and userspace improvements for firmware 1.5.13, with uninstall/rollback and resource tests. Label this accurately as OEM-based.
4. **Experimental custom image:** only after legally usable vendor inputs and matching kernel modules are available; test 5G and Wi-Fi before VPN/proxy features.
5. **Maintained OpenWrt target:** port board and modem support to a supported kernel/release, then submit clean patches through [OpenWrt's device-support process](https://openwrt.org/submitting-patches).

## Contributions sought

- Owners willing to provide **redacted** hardware revision, firmware version, `/proc/mtd`, device-tree compatible strings, and boot logs.
- Developers familiar with MediaTek MT6890/T750, CCCI/MIPC, MT7915, NAND/UBI, and A/B boot metadata.
- A legitimately obtained corresponding source release for the X28's GPL-covered components, and clarification of redistribution rights for proprietary pieces.
- Owners of spare X28 units who can validate recovery and test images independently.

**Do not post:** raw flash backups, IMEI, MAC addresses, serial numbers, SIM data, keys, passwords, calibration data, or vendor binaries with unclear distribution rights.

This brief is a draft for community discussion. It has not been posted or represented as official OpenWrt support.
