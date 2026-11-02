# X28 mainline roadmap

Investigation: 2026-11-01. Proposed engineering work, not authorization to execute
it. Preserve the current slot-A OpenWrt and stock slot B. This investigation
changed documentation only and performed read-only SSH inspection.

The smallest first implementation is an **offline, pinned ARM64 kernel build
and initramfs artifact**, with an explicit MT6890 boot-contract/memory ledger.
Its first hardware milestone is a UART prompt from an initramfs-only kernel
using a separately proven temporary boot path. A new flash image, cellular data
and a permanent recovery-slot conversion are later milestones.

## Ordered milestones and exit evidence

| Order | Deliverable | Dependencies / exit evidence |
|---|---|---|
| 0 | Reconciled boot contract and private evidence bundle | Fresh FDT, live OF properties, `/proc/iomem`, config, platform bindings, PSCI/CPU/timer/UART and LK tag/reservation inventory agree; discrepancies are explicit |
| 1 | Pinned offline Linux 6.x ARM64 Image + minimal initramfs + build manifest | Repeatable toolchain/config/source hashes; UART/GIC/timer support selected; artifacts unpack/inspect correctly; no hardware action |
| 2 | Proven load-and-return plan | Understand LK authentication/container acceptance and a temporary boot mechanism; verified backup, UART capture and tested recovery available; owner approval for any action affecting device |
| 3 | Serial-only initramfs boot | Correct RAM exclusions, CPU handoff, GICv3/timer and UART; shell reachable, no storage mounts or modem services; clean capture and return to original installation |
| 4 | MT6890 foundational drivers | Clock/pinctrl/genpd/reset/secure-firmware resources modeled and reviewed; IRQ and power behavior validated; watchdog/thermal policy safe for longer operation |
| 5 | NAND read compatibility | Chip geometry, ECC/OOB/randomizer/bad-block/PMT mapping compared offline and by read-only tests; partition offsets/names and logical content agree with backup |
| 6 | Ethernet MAC + switch | MT6890 MAC/PCS/MDIO port, then MT7531 DSA; known CPU/user port map, VLAN/isolation, LAN access; no modem dependence |
| 7 | PCIe + MT7915 through mt76 | PCIe/PHY/MSI/reset/clock support, exact PCI identity, preserved EEPROM/calibration, correct MCU firmware; association, regulatory settings and stability verified |
| 8 | Internal modem lifecycle and CCCI control | LK firmware/tag handoff retained, reservations protected, SMC/power/CCIF/FSM/watchdog and NV/fs service ABI verified before any radio action |
| 9 | DPMAIF + CCMNI / eventual WWAN integration | Descriptor/address/cache/IRQ equivalence proved; queues register without data loss; owner-approved bearer test establishes controlled TX/RX and cleanup |
| 10 | Reproducible OpenWrt target | Pinned release/kernel target, DTS/profile/packages/image manifests and firmware ownership; netifd/modem integration, DSA, mac80211 and firewall tested |
| 11 | Persistent install / recovery / upgrades | Separate reviewed plan, guarded write tooling, complete verification/rollback rehearsal; only then consider image signing policy, slots or sysupgrade changes |

No time estimates: matching source availability and platform bootability remain
unknown. Each exit gate is evidence, not a task count. Storage and networking
can be developed offline after foundations are understood; neither needs to
block a UART-only initramfs artifact.

## 0–3: first safe slice

Before writing a board DTS, reconcile the FDT's overlapping 1 GiB `/memory`
and 488 MiB `/memory@40000000` with effective System RAM and reserved regions.
Live OF MD reservations match the saved DT, but `/proc/iomem` shows an effective
reservation beginning 2 MiB earlier ([hardware report](x28-hardware-architecture.md#memory-and-boot-handoff)).
Record AP and MD physical/translated addresses, cached/noncached windows,
LK tag location, ATF/tinysys/Wi-Fi reservations, DMA address width, GIC resources,
CPU enable method and timer frequency. Never mark a live MD region as free RAM.

Establish UART hardware voltage and pinout using existing recovery evidence;
the repository warns it may be 1.8 V. Existing log capture is 921600 8N1.
Verify the actual console UART resource, baud clock, pinmux and earlycon
support; `ttyS0` in the command line alone does not identify a physical MMIO
address. The stored UART nodes have upstream `mediatek,mt6577-uart` fallback,
but their vendor clock providers still need attention. For the minimal test,
prove a safe clock strategy rather than copying unknown clock IDs.

The offline artifact should contain only a static shell/init and essentials
for serial diagnostics. Keep automatic modem startup, UBI attachment, writable
mounts and OpenWrt first-boot scripts out of that experimental initramfs. Keep
all bootloader firmware and secure-monitor binaries intact. A manifest should
record source revision, patch list, toolchain, `.config`, Image/initramfs/DTB
hashes and expected boot assumptions. A full router image is unnecessary here.

**Do not assume RAM boot exists.** The repository has not established an
acceptable temporary boot command for an arbitrary new Image/DTB/initramfs.
Inspect/document LK's load/container/authentication behavior offline first.
UART access or preloader SBC-off status does not prove a modified kernel will
be accepted. See [LK authentication preview](lk-boot-auth-preview.md#binary-patch-versus-rebuilding),
[UART evidence](uart-boot-log.md) and [BOOT-FLOW](../BOOT-FLOW.md).
Do not patch LK, switch slots, disable verification or test a reboot as part of
milestone 1. If no nonpersistent path is available, stop hardware progression
and prepare a separate owner-reviewed experiment; do not silently use flash.

First hardware success means a captured serial shell with coherent RAM/timer
and IRQ state followed by a proven return to the original boot. It does not
mean storage, four CPUs, Ethernet, Wi-Fi, power management or 5G all work.
Report each separately.

## 4–7: platform, storage and networking

Use the local SDK as a register/sequence reference, not a drop-in DTS:

- Clocks: `sdk-fg360/release_sdk/mtk/ext_kernel-4.19/drivers/clk/mediatek/clk-mt6890.c:2570`.
- Domains: `drivers/soc/mediatek/mtk-scpsys.c:2457` in that kernel.
- Modem-specific power/SMC dependencies:
  `drivers/misc/mediatek/eccci/mt6890/md_sys1_platform.c:57,487,556,601`.
- NAND: saved `nfi@11005000` is `mediatek,mt6880-nfc`; config enables
  NANDX v2 and PMT parsing, not the ordinary upstream MTK NAND driver
  ([config lines 1493,1514,1569](../firmware/kernel-4.19.205-x28.config#L1493)).

NAND must initially remain unmounted/read-only in experimental kernels. Compare
ECC-decoded logical data as well as physical page/spare geometry; raw-versus-
logical hash differences are not automatically corruption or equivalence.
Do not run UBI attachment merely to “inspect”: attachment and mount paths may
have write/recovery side effects. Do not format, run repair tools, rewrite PMT
or touch unit identity/calibration. Generic UBI is reusable only after the MTD
layer is correct. Review the vendor ubiblock/rootfs authentication delta before
claiming existing images boot unchanged.

Port MAC/MDIO/PCS resources before DSA. Use the recorded MT7531AE identity,
physical port/CPU link map and switch reset constraints; preserve management
reachability and VLAN isolation. A DSA conversion changes interface names and
OpenWrt network defaults, so test it in a disposable config first. Omit hardware
NAT initially; measure software forwarding before deciding acceleration scope.

For MT7915, prefer mt76 after PCIe host operation is proven. Preserve the unit's
EEPROM/e2p calibration, antenna/regulatory configuration and required MCU
firmware. Replace vendor `.dat`/`iwpriv` integration with mac80211 configuration;
do not copy vendor WARP/offload blindly. Validate each band, association,
reconnect, sustained traffic and thermal behavior on a bench setup with a
second internet path. These tests are not authorized by this research request.

## 8–9: modem progression

Start with the source graph in [driver analysis](x28-modem-driver-analysis.md).
Seek the exact X28 GPL tree/deltas and compare them with FG360 before porting.
Keep modem firmware, LK tags, NV data and trusted firmware unchanged initially.
Do not introduce a new firmware loader while also changing the transport.

Separate achievements:

1. OF probe/resources/CCCI char-device registration, with no automatic reset or
   radio command. Mapping or probing hardware can itself affect state; test
   only within the approved bench experiment.
2. Correct shared-memory layout, CCIF interrupt/ring operations and lifecycle
   ABI, including error handling. Establish `ccci_fsd` and NV requirements.
3. Preserve the vendor userspace ABI initially: device names, ioctl structure
   layouts, mmap boundaries and MIPC versions. Run no vendor binary with
   undocumented flags. The live `ql_ril_service` PID absence is not permission
   to remove the startup dependency.
4. DPMAIF generation/MED descriptors, DMA mappings, cache barriers, queue
   ownership and interrupt handling, then net-device registration. Do not
   substitute t7xx registers because the block name matches.
5. Owner-approved single bearer test with netifd, bounded traffic and cleanup;
   compare CID/ifname/address behavior with the working `x28_mipc` protocol.
6. Only on recoverable hardware, separately approve cold-start/reset/recovery,
   SIM/network loss, IPv4/IPv6, repeated activation and sustained traffic tests.
   Preserve thermal/RF power protections.

WWAN core can eventually replace product-specific network/port exposure where
it fits. It does not translate MIPC to MBIM. An open userspace replacement needs
protocol/version documentation, NV/fs behavior and tests; source visibility
under a proprietary SDK header is not an upstream contribution licence.
Keep SMS/voice/audio out of the first data milestone unless a verified runtime
dependency requires them.

## 10–11: OpenWrt and rollback

Keep source/toolchain/config/DT/image manifests reproducible. Separate public
integration code from privately supplied firmware; document exact hashes and
licence/redistribution status. Add an MT6890 target/profile only after platform
support is real. Retain the existing public netifd/LuCI protocol where its
backend ABI remains valid; replace it explicitly if the driver API changes.
Use the selected OpenWrt release's kernel ABI, firewall and package build rules;
never mix stock 4.19 `.ko` files with a Linux 6.x kernel.

Rollback prerequisites before any later boot/write experiment:

- Verified per-partition backups and a second off-device copy; preserve NV,
  identity, carrier and calibration data, not just rootfs.
- Tested UART and the proven download-agent/read/restore setup, using existing
  guarded recovery tools. Never change their code mid-session: receipts bind
  tool hashes. No ad-hoc `dd`/MTD write path.
- Exact slot/counter baseline and reversal plan. A boot increments slot tries;
  current `x28-bootok` handles them on successful boots. Stock B can repair/erase
  A when counter conditions are met; a “fallback” is not automatically benign.
- `misc` recovery over the download agent remains unproven. Do not claim a
  full recovery path for metadata changes. Existing stock B stays intact during
  this program; converting it into a rescue slot is a distinct future project.
- Kernel/container/rootfs signature acceptance resolved in the plan, without
  changing verified-boot policy as a convenience.

Authoritative project procedures: [RECOVERY](../RECOVERY.md),
[BOOT-FLOW](../BOOT-FLOW.md), [native boot prerequisites](live-native-boot-prerequisites.md),
[rootfs write plan](rootfs-a-write-plan.md) and [BUILD](../BUILD.md).
These references describe guarded operations; linking them is not an
instruction to execute them now.

## Not verified

No build/boot, modem reinitialization, flash write, DT modification, traffic
benchmark or rollback rehearsal was performed for Linux 6.x. The next safe
engineering action is milestone 0 and an offline artifact build, not flashing
or replacing the working installation.
