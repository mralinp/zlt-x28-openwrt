# X28 mainline kernel feasibility

Investigation: 2026-11-01. Read with [hardware evidence](x28-hardware-architecture.md)
and [vendor source trace](x28-modem-driver-analysis.md). No Linux 6.x kernel was
built or booted in this investigation. Compatibility conclusions below are
source comparisons and engineering assessments, not hardware test results.

## Decision

**A modern kernel is plausible, but neither a stock mainline boot nor working
5G on Linux 6.x is demonstrated.** This is an MT6890 platform bring-up plus an
internal modem driver port. Upgrading OpenWrt userspace has already succeeded;
that does not demonstrate a new kernel. Recommend **Strategy C**, using
upstream drivers where hardware matches, and a deliberately bounded forward
port of the internal modem stack where no matching upstream driver was found.

The working link is CCIF shared-memory control plus DPMAIF packet DMA, exposed
as CCCI char devices and CCMNI network interfaces. It is not the PCIe host
interface supported by `mtk_t7xx`. Shared transport names are useful reference
material, not register, firmware protocol or boot ABI compatibility.

## Research boundary and reproducibility

External network access worked. Browser fetches and public GitHub source API
reads were used; several raw GitHub requests returned 429/cache errors, and
those failures were not treated as source evidence. Sources include Linux
**v6.12** as a reproducible Linux 6.x baseline, and a mainline tree API snapshot
whose root SHA was `cbbddb6b08cc9900a87cccaa9b22bbe06aa4f50a`.
The recursive tree result was explicitly **truncated**, ending under
`drivers/usb/gadget/`; the inspected `Documentation/`, `arch/arm64/`,
`drivers/clk/`, `drivers/net/`, `drivers/remoteproc/` and `drivers/mailbox/`
prefixes precede that cutoff. No MT6890/ECCCI/CCMNI path was found there.
A filename search cannot rule out an implementation under another name.

The current mainline compatible tables were also read for `mtk_eth_soc.c`,
`mtk_scp.c`, `mtk-cmdq-mailbox.c`, the NAND binding and WWAN Kconfig. These did
not establish MT6890 support. This report does not claim an exhaustive audit
of every public fork or mailing-list patch. Use the pinned links below to
recheck scope before implementation; do not assume future mainline is unchanged.

## Compatibility matrix

Effort is qualitative and conditional: **integration** means an existing driver
matches the hardware identity but needs board resources; **platform port**
means hardware-specific support remains; **subsystem port** includes hardware,
firmware and userspace contracts. No calendar estimates are justified yet.

| Candidate / inspected version | Supported hardware and dependencies | X28 compatibility and missing work | Assessment |
|---|---|---|---|
| Vendor ECCCI + CCMNI, local SDK 4.19.190 | MT6890 generation 6297 source; clock/genpd/SMC/EMI/shared-memory/CCCI utility dependencies | Matches observed compatible names and transport; exact Quectel/Tozed changes missing; not ABI-identical to 4.19.205 | Best modem starting point; substantial subsystem port |
| `mtk_t7xx`, available by 5.19 and in 6.12 | MediaTek T700 PCIe host modem; PCI, WWAN; MBIM/AT ports, CLDMA/DPMAIF and PCIe PM | No platform OF match for internal `mediatek,mddriver`; X28 has no enumerated T700 modem; MMIO layout, IRQ, power and control ABI differ | Reference algorithms only until hardware/protocol equivalence is proved; major adaptation |
| Linux WWAN core, 6.12/current inspected | Hardware-independent char-port/network-link framework, driver callbacks and rtnetlink | Can be a future API for an X28-specific driver; supplies no CCIF, DPMAIF, MD boot or MIPC implementation | Reusable framework; integration after transport works |
| Public Android MediaTek CCCI/ECCCI trees | Vendor generation/SoC-specific drivers, often Android dependencies | Project listing contains old 3.10/3.18/4.4 branches; no matching X28 source established by that listing | Historical reference; verify each branch/generation/licence, never substitute by name |
| `mtk_scp` remoteproc, 6.12/current inspected | MediaTek SCP auxiliary processors; remoteproc, IPI and SoC-specific firmware/memory resources | Match tables cover SCP platforms, not MT6890 MD1; CCCI rings are not proven RPMsg/virtio channels | Not a modem replacement; a new backend would still be substantial work |
| `mtk-cmdq-mailbox`, current inspected | MediaTek GCE command-queue engines and matching SoC definitions | GCE mailbox is not CCIF modem transport; X28 generic vendor GCE binding differs from upstream SoC binding | No automatic reuse for modem; establish actual mailbox hardware first |
| GICv3, ARM architected timer, PSCI, MediaTek 8250 UART, 6.x | Standard ARM64 facilities; firmware handoff, clock and interrupt resources required | GIC/timer and UART fallback compatible exist in stored DT; PSCI/conduit and UART clocks/address must be verified against boot contract | Strong candidates for minimal boot; no boot proof |
| MediaTek clocks/pinctrl/genpd/reset, current inspected | SoC-specific register tables/bindings | No MT6890 platform set established; SDK has `clk-mt6890.c` and `mtk-scpsys.c` MT6890 matches absent from the inspected upstream platform paths | Foundational platform port; not a DTS-only change |
| `mtk_eth_soc`, 6.12/current inspected | MT2701/7621/7622/7623/7629/7981/7986/7988 and rt5350 entries in current inspected match table; DMA, MDIO, PCS/phylink, clocks/resets | No `mediatek,mt6890-eth` match; NETSYS/PDMA/QDMA/SGMII and register differences must be compared | Platform port; working MT7531 DSA alone does not provide the MAC |
| `mt7530` DSA with MT7531 support, 6.12 | MT7530/MT7531 switch, MDIO, DSA/phylink, CPU-port topology/reset | Older live audit identifies MT7531AE; vendor DT is `mediatek,mt753x`, not upstream binding; translate port wiring/VLAN policy and validate 2.5G CPU links | Good reuse candidate after MAC/MDIO; board integration |
| `mt7915e` / mt76, 5.9+; current OpenWrt mt76 inspected | PCI ID 14c3:7915; PCI, mac80211, mt76/connac, MCU firmware and EEPROM | Exact PCI identity observed; requires MT6890 PCIe/PHY/MSI and board calibration extraction; vendor `.dat`/iwpriv configuration does not transfer | Good reuse candidate; integration depends on host platform; no throughput promise |
| MediaTek raw NAND/ECC (`mtk_nand`), 6.x/current binding | `mediatek,mt2701-nfc`, `mt2712-nfc`, `mt7622-nfc`; clocks and ECC engine | X28 says `mediatek,mt6880-nfc`, has two MMIO resources/IRQs and NANDX v2; ECC/OOB/randomizer/bad-block layout and vendor PMT parsing unverified | Storage platform port or proven compatibility extension; never alias blindly |
| MTD/UBI/UBIFS/ubiblock/SquashFS, 6.x | Generic storage layers above a correct MTD implementation | Reusable once NAND geometry/ECC and partition discovery match; does not implement vendor PMT or Quectel signed-rootfs policy | Standard upper layers; offline image/read-only validation first |

Sources supporting individual driver scope:

- [Linux 6.12 t7xx documentation](https://www.kernel.org/doc/html/v6.12/networking/device_drivers/wwan/t7xx.html),
  [5.19 WWAN driver index](https://kernel.org/doc/html/v5.19/networking/device_drivers/wwan/index.html),
  [6.12 WWAN Kconfig, MTK_T7XX lines 97–108](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wwan/Kconfig#L97).
- [6.12 t7xx PCI binding/probe](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wwan/t7xx/t7xx_pci.c),
  [6.12 WWAN core](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wwan/wwan_core.c).
- [Android MediaTek repository branch listing](https://android.googlesource.com/kernel/mediatek/).
  Its default branch is an empty initial repository; select a real branch before
  drawing source conclusions. The branch listing is not MT6890 enablement evidence.
- [Current inspected SCP matches](https://github.com/torvalds/linux/blob/cbbddb6b08cc9900a87cccaa9b22bbe06aa4f50a/drivers/remoteproc/mtk_scp.c#L1588),
  [current inspected GCE matches](https://github.com/torvalds/linux/blob/cbbddb6b08cc9900a87cccaa9b22bbe06aa4f50a/drivers/mailbox/mtk-cmdq-mailbox.c#L855),
  [6.12 MediaTek UART](https://github.com/torvalds/linux/blob/v6.12/drivers/tty/serial/8250/8250_mtk.c).
- [Current inspected Ethernet match table](https://github.com/torvalds/linux/blob/cbbddb6b08cc9900a87cccaa9b22bbe06aa4f50a/drivers/net/ethernet/mediatek/mtk_eth_soc.c#L5682),
  [6.12 MT7530/MT7531 binding](https://github.com/torvalds/linux/blob/v6.12/Documentation/devicetree/bindings/net/dsa/mediatek,mt7530.yaml),
  [local MT7531AE identification, DEVICE-AUDIT line 14](../DEVICE-AUDIT.md#L14).
- [Linux Wireless MT7915 version/support list](https://wireless.docs.kernel.org/en/latest/en/users/drivers/mediatek.html),
  [OpenWrt mt76 PCI IDs](https://github.com/openwrt/mt76/blob/master/mt7915/pci.c#L19),
  [mt7915 Kconfig](https://github.com/openwrt/mt76/blob/master/mt7915/Kconfig).
- [Current inspected raw NAND binding](https://github.com/torvalds/linux/blob/cbbddb6b08cc9900a87cccaa9b22bbe06aa4f50a/Documentation/devicetree/bindings/mtd/mediatek,mtk-nfc.yaml),
  [6.12 UBI implementation](https://github.com/torvalds/linux/tree/v6.12/drivers/mtd/ubi),
  [6.12 UBIFS implementation](https://github.com/torvalds/linux/tree/v6.12/fs/ubifs).

## What actually blocks a modern modem

1. **Platform foundations.** The boot chain's memory fixups/reservations, GIC,
   CPU enable method, timer and UART must work before modem work is testable.
   MT6890 clock gates, pin control, power domains, sleep/EMI access and secure
   firmware services need matching implementations. The tree has overlapping 1 GiB and 488 MiB memory nodes, and effective
   reservations differ from their DT descriptions; treating one node as the
   complete boot memory contract risks silent corruption.
2. **Lifecycle and firmware handoff.** LK loads MD firmware and passes private
   tags. Preserve that contract before considering a replacement loader. The
   SDK uses `MTK_SIP_KERNEL_CCCI_CONTROL` and runtime power management; a modern
   kernel with generic remoteproc enabled does not supply these operations.
3. **Internal control and data drivers.** Port CCIF rings, CCCI channel/proxy/FSM
   logic, DPMAIF generation/MED descriptor and DMA paths, CCMNI integration,
   IRQ and exception handling. Mainline t7xx's PCIe resource mapping/PM and
   MBIM/AT model are not the observed native MIPC/CCCI ABI.
4. **Exact source and kernel ABI.** SDK-derived objects cannot safely substitute
   for stock binaries: the existing CRC investigation found 19 differing and
   two absent exports among 35 needed symbols. This was a TPROXY comparison,
   not a modem-specific CRC test, but rules out assuming whole-tree identity.
   Rebuild kernel components against the new kernel; do not force vermagic or
   symbol CRCs. See [kernel-module-crc.md](kernel-module-crc.md).
5. **Userspace/NV contract.** Existing AArch64 musl binaries may be usable if
   their device/ioctl/mmap ABI and library closure are preserved. They do not
   require the exact kernel release merely by being userspace. Compatibility
   is unproven until the actual ioctls/structures, device names and startup/NV
   operations are compared. Quectel libraries, modem filesystem services and
   calibration cannot simply be removed.
6. **Proprietary boundaries.** Kernel-side transport source exists in the SDK;
   matching X28 deltas are missing. MIPC and some CCCI userspace source exists
   but has restrictive headers. MD firmware remains a binary dependency even
   with an upstream-quality host driver. A fully redistributable image needs
   an explicit firmware/licence plan; replacing a host driver alone does not
   resolve it.

## Kernel API incompatibilities to audit

These are concrete porting surfaces, not claimed compiler failures from a 6.x
build (none was attempted):

| Vendor source surface | Modernization required |
|---|---|
| `ccmni.c:1611–1617` four-argument `netif_napi_add` | Target 6.x NAPI API/weight registration; retain GRO and budget semantics |
| `ccmni.c:528,685,2059` `netif_rx_ni` calls | Replace removed receive API according to execution context, not textual substitution alone |
| `ccci_hif_dpmaif.c:4041` legacy tasklet setup and work threads | Check selected kernel's supported tasklet API, teardown synchronization and interrupt context |
| Direct sk_buff use / vendor networking hooks | Audit header/structure differences and acceleration hooks; use upstream networking interfaces |
| `mt6890/md_sys1_platform.c` runtime PM, clocks, custom PM QoS/PMIC and SMC headers | Replace missing vendor APIs; retain modem domain sequencing and firmware ABI |
| CCCI shared memory and DMA maps | Preserve address translation, cache coherency, DMA masks, barriers and descriptor ownership |
| CCCI fops/ioctls/proc/sysfs | Audit uaccess, compat layout, lifetime and removed helper APIs; retain existing userspace ABI initially |
| Vendor NANDX, PMT, YAFFS2 and Quectel ubiblock authentication changes | Isolate from initramfs proof; do not assume ordinary upstream UBI can mount all vendor data |

Hardware behavior must remain intact while APIs change. “It compiles” is not
proof of correct modem power, DMA memory ownership or cold-start handling.

## Strategy comparison

| Dimension | A: forward-port vendor stack | B: adapt upstream drivers | C: staged hybrid migration |
|---|---|---|---|
| Feasibility | Plausible with matching source/deltas; current SDK is incomplete evidence | Strong for Wi-Fi/switch/frameworks; no direct upstream internal-modem binding found | Most defensible: platform proof first, modem later |
| API cost | High: 4.19 vendor hooks, char ABI, networking and PM | Lower for matching peripherals; high for t7xx/internal-modem adaptation | Same real work, ordered so failures are isolated |
| Hardware coupling | Retains vendor generation/platform assumptions | Requires new MT6890 resources/backends and verified descriptor/protocol reuse | Starts with UART/RAM, adds each verified subsystem |
| Binary dependencies | Retains MD firmware and initially Quectel/MIPC/NV userspace | Firmware remains; MIPC does not become MBIM automatically | Retains required blobs first; replace only with measured equivalents |
| Complexity / maintenance | Large downstream patch burden and exact-source gap | Smaller long-term surface where upstream matches; modem support is still substantial new work | Manageable increments, but transitional interfaces must be tracked |
| Upstream acceptance | Low for an unchanged vendor dump; needs decomposition, DT schemas and removal of product policy | Best for hardware-backed extensions and standard WWAN interfaces | Good route to reviewable platform/peripheral patches; not automatic acceptance |
| Risk to current install | High if attempted as a direct replacement | High if compatibility assumptions drive a flash | Lowest when builds are offline and early boots use a separately proven temporary path |

Recommendation: C, with B for MT7915/MT7531 and generic facilities; use A only
for the smallest source-backed internal modem implementation needed. Do not
forward-port unrelated UI, Wi-Fi acceleration, Android debug or audio code to
get the first serial prompt. Do not discard thermal/power or calibration
requirements for a production modem.

## OpenWrt implications

The fetched [current MediaTek target Makefile](https://github.com/openwrt/openwrt/blob/main/target/linux/mediatek/Makefile)
lists `filogic mt7622 mt7623 mt7629` and `KERNEL_PATCHVER:=6.18`; it does not
establish an MT6890 target. The existing repository's `x28_mipc` packages are
userspace integration, not an upstream device profile. Keep a Linux 6.x
baseline pinned for experiments and use the chosen OpenWrt release's supported
kernel when doing target integration. Neither changing the target string nor
reusing a Filogic image supplies MT6890 drivers.

A maintainable port needs board DTS/bindings, reproducible kernel config/build,
firmware manifests and calibration handling, correct storage/partition parsing,
DSA/mac80211 integration, a modem ABI strategy and a guarded image/recovery path.
The [roadmap](x28-mainline-roadmap.md) orders these without requiring flash or a
reboot during research.
