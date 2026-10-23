# Native OpenWrt port tasks — ZLT X28

This replaces the earlier OEM-enhancement-first task ordering. The controlling objective and ownership rules are in `PROJECT-PLAN.md`.

## A. Establish the hardware boundary

- [x] Confirm installed standard network binaries and native MIPC protocol hooks.
- [x] Identify active vendor LAN/WAN managers and missing netifd wireless integration.
- [x] Audit the installed MIPC helpers as text, without executing setup/teardown.
- [ ] Trace the minimal modem boot/CCCI/MIPC service dependency graph.
- [ ] Measure the MT7531 physical port/CPU/VLAN map; preserve board calibration.
- [ ] Inventory exact kernel config, module ABI, source availability and required blobs.
- [ ] Choose a buildable OpenWrt/kernel baseline; do not assume current upstream modules fit 4.19.

Acceptance: every retained vendor component has a hardware reason; LAN, routing, DHCP and firewall policy have standard OpenWrt owners in the target design.

## B. Prepare the clean build

- [ ] Pin upstream source and create a Linux build environment matched to the required toolchains.
- [ ] Obtain or replace the missing board/kernel build inputs.
- [ ] Build a minimal rootfs using upstream netifd, procd, dnsmasq/odhcpd, firewall and LuCI.
- [ ] Exclude OEM CGI, credential proxy, UI wrapper bundles and competing LAN/WAN policy managers.
- [ ] Verify ELF ABI, runtime libraries, kernel requirements, image format and licensing.

Acceptance: reproducible rootfs/build manifest; unresolved kernel or signing inputs explicitly prevent calling it a bootable firmware image.

## C. Prove standard wired routing on a recoverable test device

- [ ] Establish UART/USB restore and fallback internet before boot/network ownership trials.
- [ ] Create verified UCI LAN/WAN/bridge configuration from the measured board topology.
- [ ] Verify `network.interface.lan` status, native DHCP/DNS, firewall policy and ordinary LuCI Save/Apply.
- [ ] Verify reboot, rollback and absence of competing vendor policy writers.

Acceptance: stock OpenWrt services own the wired router. A renamed menu or a status-only shim does not pass.

## D. Implement the native cellular boundary

- [ ] Capture/document read-only modem capability and bearer response formats.
- [x] Write a source-only IPv4 netifd handler (mock-tested) to remove global `killall`, implicit APN teardown, UCI firewall/DHCP edits and process-wide policy effects.
- [x] Validate UCI input (mock-tested) and bearer responses; track only the interface's own bearer.
- [x] Report dynamic device (mock-tested), addresses, routes, DNS and failure state via native netifd notifications.
- [ ] Test with mocked modem responses, then validate cold boot, reconnect, IPv4/IPv6 and ifup/ifdown on recoverable hardware.

Acceptance: the standard Interfaces page and netifd API operate the cellular link without OEM CGI or a custom core LuCI page. Setup/teardown does not rewrite DHCP/firewall policy.

## E. Implement native wireless integration

- [ ] Evaluate upstream mt76 against the actual board/kernel/calibration requirements.
- [ ] If retaining the hardware driver for bring-up, implement its native netifd wireless lifecycle with UCI as the source of truth.
- [ ] Verify status, SSIDs/security/channel/regulatory settings, bridge membership and reload/teardown.
- [ ] Validate standard LuCI Wireless with no separate vendor controller.

Acceptance: netifd owns radio/interface lifecycle; stock LuCI changes reach the driver and survive reboot.

## F. Finish, profile and release

- [ ] Ship the standard LuCI network pages with proven native service backends.
- [ ] Build matching WireGuard/OpenVPN/proxy dependencies and verify selective routing/DNS.
- [ ] Measure idle/load RAM, CPU, thermals and throughput after removing unneeded vendor services.
- [ ] Prove restore and independent installation on another unit.
- [ ] Release original source/recipes with provenance and measured limitations.

No full-image build or native ownership migration has yet passed. The prior LuCI customization work is historical OEM UI work, not completed port tasks.

## Native prototype checkpoint — 2026-10-21

Original source is in `../package/`. All 31 mocked lifecycle cases and local LuCI checks passed. No IPK/image build, hardware lifecycle test or live ownership migration has passed. IPv4 only; recovery, cold-start, IPv6 and wireless remain open.
