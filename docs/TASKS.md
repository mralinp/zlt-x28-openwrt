# Tasks — native OpenWrt on the ZLT X28

Status as of 2026-10-29 (release `v0.22.0`). The goal and rules are in [PROJECT-PLAN.md](PROJECT-PLAN.md); where things
stand is in [STATUS.md](STATUS.md). Work items live in GitHub issues; this list is the overview.

## A. Hardware boundary

- [x] Confirm installed network binaries and the native MIPC protocol hooks.
- [x] Identify the vendor LAN/WAN managers and the missing netifd wireless integration.
- [x] Trace the minimal modem start order (nvram, ccci, ril, netd, atci) and what it needs (yaffs2 mounts, USB gadget).
- [x] Measure the MT7531 port/CPU/VLAN map; keep the board calibration.
- [x] Inventory the kernel config, module ABI and required blobs ([FIRMWARE-INVENTORY](FIRMWARE-INVENTORY.md)).
- [x] Choose a buildable baseline: OpenWrt 23.05.5 userspace on the vendor 4.19.205 kernel.
- [ ] Obtain the vendor's GPL source (kernel and OpenWrt tree) in writing.

## B. Clean build

- [x] Build the open userspace in CI (ImageBuilder, fw3, LuCI) and boot-test it in QEMU on every build.
- [x] Stage the private rootfs from the owner's backup, add the first-boot profile, package the UBI.
- [x] Exclude the OEM CGI, credential proxy and competing policy managers; refuse boot paths that can write flash.
- [x] Verify ELF ABI and runtime libraries of the vendor stack.
- [ ] Publish a reproducible build manifest and a how-to for other owners.

## C. Wired routing

- [x] UART and USB restore working before any boot trial.
- [x] LAN bridge, DHCP/DNS, IPv6 on the LAN, firewall and NAT owned by stock OpenWrt services.
- [x] Settings, host keys and the root password survive reboots (`S95done`).
- [ ] NAT and throughput measured with real LAN clients.

## D. Cellular

- [x] Native netifd protocol with its own LuCI page; IPv4, IPv6, IPv4v6, APN from the SIM.
- [x] Cold start at boot, link-up handling, reconnect re-binding of NAT.
- [ ] SIM PIN, PAP/CHAP, and other operators or SIMs.
- [ ] Long-run reconnect behaviour after modem resets or link loss.

## E. Wireless

- [x] Native netifd handler for the vendor `mt_wifi` driver; both radios up with WPA2, default config at first boot.
- [ ] Client tests, throughput, regulatory settings, bridge membership and reload.
- [ ] Evaluate upstream `mt76` against this board and kernel (the vendor driver is what runs today).

## F. Stable release (roadmap)

- [ ] 48 h soak with no unexplained reboots; idle CPU and RAM baseline; explain the load average of ~3 on an idle CPU.
- [ ] **Recovery slot** on B: small kernel and rescue path that installs OpenWrt on A and can restore stock; frees the
      flash that holds a second full firmware. Prove it, then retire the stock copy.
- [ ] `sysupgrade` for the new layout.
- [ ] Stable tagged release; OpenWrt wiki device page; build documentation.
- [ ] Prove restore and independent installation on another unit.

## G. Later

- [ ] Fan control from LuCI ([#47](https://github.com/mralinp/zlt-x28-openwrt/issues/47)).
- [ ] Local SMS and voice on the native image (worked on the stock overlay; voice blocked by the SIM).
- [ ] Own 4.19 kernel and kmod feed from a sibling-device SDK ([#130](https://github.com/mralinp/zlt-x28-openwrt/issues/130)); not tried yet.
- [ ] WireGuard/OpenVPN/proxy dependencies matching the kernel, and selective routing.

## Known open questions

- Slot A is unconfirmed (success 0) on purpose; whether the preloader treats success 1 differently is unknown
  ([BOOT-FLOW](BOOT-FLOW.md)).
- The download-agent block write to `misc` was never acknowledged; there is no proven off-device `misc` rewrite.
