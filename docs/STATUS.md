# Project status — 2026-10-21

## Objective

A real OpenWrt port: stock LuCI/UCI, netifd, standard DHCP/DNS and a kernel-compatible firewall own networking. OEM CGI wrappers and a UCI-to-vendor sync adapter do not satisfy this objective. Preserve the working modem, board calibration and SIM-unlocked operation.

## Completed evidence

- Root SSH and LuCI access existed before this migration.
- A private backup of all 51 NAND partitions was previously captured and hash-verified. This does not establish a tested restore.
- One device was identified as MT6890/T750, ARM64, OEM 1.5.13, Linux 4.19.205, OpenWrt 19.07-derived userspace. Hardware revision is not established.
- Read-only audit found vendor network owners, stale UCI values and missing native wireless integration.
- Original IPv4 `x28_mipc` netifd protocol source and normal LuCI protocol addon exist under `package/`. 31 mocked lifecycle cases passed with the device's real OpenWrt shell/JSON helpers. All modem and network notification calls were mocked. Local JS and shell checks passed. No IPK/image build or real activation passed.
- Historical resource display changes and OEM UI integrations are preserved under `experiments/oem-ui/`.

## Current live-device state at last observation

- Existing LuCI: port 4153. The custom read-only mock preview is `/admin/status/x28_native`. The user rejected that presentation as unlike genuine stock LuCI.
- The separate port 4154 stock-view experiment is broken; see its README. Its temporary procd service was stopped during migration. It must not be described as completed.
- Vendor WAN manager and the default cellular route remained active in the last network check. No native protocol handler was installed. This is a timestamped observation, not a live health claim.
- No flash, reboot, network ownership takeover or modem activation was performed for these prototypes.

## Known blockers

No vendor SDK/external kernel source, proven UART/USB recovery or validated clean image build. Physical switch map, modem startup dependencies, proprietary redistribution rights, IPv6, wireless lifecycle, reconnect, thermal/throughput improvements and matching VPN dependencies remain unresolved.

## Next work on the laptop

1. Repair/validate the isolated genuine LuCI preview; do not deploy mock pages as proof of a port.
2. Keep private firmware dumps outside Git. Inventory partition/source provenance and hashes; extract copies offline.
3. Audit minimal modem boot/CCCI/MIPC dependencies and measure switch topology through safe reads.
4. Select a buildable userspace/kernel baseline and a Linux build environment. Apple Silicon macOS can host editing and tests; a Linux environment is planned for OpenWrt cross-building, not yet provisioned or validated.
5. Build clean rootfs packages, then prove restore before boot or network ownership tests on recoverable hardware.

The missing SDK is not replaced by copying a running filesystem. A firmware dump and an extracted rootfs are research inputs; they are not a rebuildable source tree.

## Offline extraction checkpoint — 2026-10-21

Boot B and rootfs B hashes were verified; rootfs system files extracted into a case-sensitive Linux volume. See `FIRMWARE-EXTRACTION.md`. This supersedes earlier notes that no extraction had occurred. No modem changes or firmware execution occurred.

## Complete partition preparation — 2026-10-21

All51 original main-data partition captures were decompressed and SHA-256/size verified (1,072,168,960 bytes); a backup-container archive was checked. See `RECOVERY-BACKUP.md`. This is not a proven flashable recovery image: OOB/YAFFS layout, live consistency and actual restore remain unresolved.
