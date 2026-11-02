# X28 modem driver analysis

Investigation: 2026-11-01. Documentation only; no firmware, DT, service, network,
boot setting or flash changes were made. No reboot, modem command, commit or push.

Evidence labels: **Observed** = read from this running X28; **Artifact** = stored
X28 DT/config/backup analysis; **SDK** = inspected Fibocom FG360 sibling source,
not the exact Quectel/Tozed build; **Assessment** = engineering inference.
SDK files are local, ignored dependencies and may not exist in a public checkout.
Line references refer to the files inspected, not a promise that later SDK versions match.

## Scope and provenance

The audit covered tracked documentation, DT/config, patches, `package/`,
`router/`, `tools/build/`, recovery/LK research, `experiments/`, vendor UI adapter
code, firmware inventories and the local FG360 kernel/modem SDK. Recovery tools
were read as architecture evidence, never invoked. Firmware images/binaries
were not executed or decompiled again; existing extraction, ELF dependency and
UART results are cited. This is a subsystem investigation, not a line-by-line
security review of unrelated applications or every SDK driver.

| Layer | Exact evidence | Limit |
|---|---|---|
| Running X28 | `uname` = 4.19.205, 2023-12-22 build; live DT matches modem compatible/flag | Exact Quectel/Tozed source tree not supplied |
| Stock kernel config | [config lines 1804–1814](../firmware/kernel-4.19.205-x28.config#L1804) | Config alone does not reveal all vendor source changes |
| Sibling source | `sdk-fg360/release_sdk/mtk/ext_kernel-4.19/Makefile:2–4`: 4.19.190 | Not a reproducible build of stock X28 |
| SDK release | `sdk-fg360/release_sdk/release_version.txt:1–8`: FG360.A12, gem-mp-1907-mp1.V1.20, 2021 | Fibocom branch, not Quectel RG500L-EU |
| Existing OpenWrt | [STATUS lines 13 onward](../STATUS.md#L13), OpenWrt 23.05.5 userspace | Working cellular still uses vendor kernel and userspace |
| Rebuild mismatch | [kernel-module-crc lines 14–18, 46 onward](kernel-module-crc.md#L14) | CRC differences prove no ABI identity, not exact field offsets |

The stock banner/compiler provenance is recorded at
[FIRMWARE-INVENTORY lines 11–15](../FIRMWARE-INVENTORY.md#L11): OpenWrt GCC 7.5.0,
`r0-f6109fc5`, vendor build host. A GPL request exists
([gpl-source-request.md](gpl-source-request.md)); its existence does not establish
that matching sources were delivered.

## Built-in versus modules

**Observed:** driver bindings are `driver_modem` and `ccci_hif_dpmaif`; neither
has a `module` symlink, and neither appears in `lsmod`. Running `/proc/config.gz`
confirms the following saved configuration:

```text
CONFIG_MTK_CCCI_DEVICES=y
CONFIG_MTK_MD1_SUPPORT=24
CONFIG_MTK_NET_CCMNI=y
CONFIG_MTK_ECCCI_DRIVER=y
# CONFIG_MTK_ECCCI_CLDMA is not set
CONFIG_MTK_ECCCI_CCIF=y
CONFIG_MTK_ECCCI_C2K=y
CONFIG_MTK_ECCCI_PLATFORM="mt6890"
CONFIG_MTK_HSAPIF_DRIVER=y
# CONFIG_MTK_PCIE_EP is not set
```

The modem core, CCCI utilities, CCMNI and ECCCI HIF objects are built into the
kernel, not proprietary `.ko` files that can be copied into Linux 6.x.
SDK `drivers/misc/mediatek/eccci/Makefile:162 onward` selects the built-in
subdirectories; `eccci/hif/Makefile:33–45` includes DPMAIF and conditionally CCIF
ring-buffer support. The config's C2K name is a build selector here, not evidence
of a second active CDMA modem (`MTK_MD3_SUPPORT=0`).

**CLDMA distinction:** `hsapif/Makefile:15–34` requires both HSAPIF and PCIe EP.
The X28 disables EP (config line 1967); its CLDMA platform device is unbound.
`hsapif/ccci_dvr_cldma.c:82,213,231` would otherwise probe
`mediatek,cldma_sys_ap`. A CLDMA node or source file does not establish that
cellular packets use it on this unit.

Loaded supporting vendor modules include `hw_nat`, `wifi_md_coex`, `mt_wifi`,
`mtk_warp`, `mtk_warp_proxy`, `conninfra`, `gps_drv`, `btmtk_uart`.
`wifi_md_coex` is coexistence, not the primary modem transport. NAT and Wi-Fi
acceleration are not prerequisites for a correct software IP path; whether
this vendor build has hard link dependencies on them must be checked before
removal. Stock module inventory and licence declarations:
[FIRMWARE-INVENTORY lines 23–34](../FIRMWARE-INVENTORY.md#L23).

## Source trace: startup and firmware ownership

All paths in this section are relative to
`sdk-fg360/release_sdk/mtk/ext_kernel-4.19/drivers/misc/mediatek/`.
They explain the sibling implementation matching observed bindings, not an
assertion of identical stock machine code.

| Step | File/function/line | Behavior and dependency |
|---|---|---|
| Driver registration | `eccci/modem_sys1.c:1629–1669`, `modem_cd_init`, `ccci_modem_probe` | OF match `mediatek,mddriver`, platform driver `driver_modem` |
| Resources/IRQs | `eccci/mt6890/md_sys1_platform.c:57–195`, `md_cd_get_modem_hw_info` | Maps CCIF, parses three modem IRQs; maps `mediatek,sleep`; clock and runtime PM integration |
| Modem registration | `eccci/modem_sys1.c:1548–1599` | `ccci_md_register`, reads `mdhif_type`, initializes selected HIF |
| LK handoff | `ccci_util/ccci_util_lib_fo.c:1202–1264`, `:1267` (`get_lk_load_md_info`) | Reads mddriver's LK modem information/tags and reports load status |
| Start | `eccci/modem_sys1.c:448–509`, `md_cd_start` | Initializes/clears shared regions; says image already ready, bypasses load; checks header; starts HIF and powers/releases MD |
| Secure/power boundary | `eccci/mt6890/md_sys1_platform.c:487–615`, `md_start_platform`, `md_cd_power_on`, `md_cd_let_md_go` | `MTK_SIP_KERNEL_CCCI_CONTROL` SMC calls, runtime PM/domain ownership and SoC-specific registers |
| Lifecycle | `eccci/fsm/ccci_fsm.c`, `ccci_fsm_ioctl.c`, `ccci_fsm_monitor.c` | Startup/handshake, watchdog/exception/reset states, char-device control ABI |

**Firmware loading answer:** live `/sys/kernel/ccci/lk_md` says LK load succeeded;
the stored UART capture shows LK authenticating `md1rom`, `md1dsp`, `md1drdi`
([uart-boot-log lines 87–92](uart-boot-log.md#L87)). The SDK kernel startup
explicitly bypasses image loading. Therefore the supported model is LK-loaded
firmware followed by Linux startup/control, not a mainline
`request_firmware()`/remoteproc loader. Exact stock reset/reload behavior is
not proven by a warm runtime snapshot. Firmware is in `md1img_a/b` (80 MiB),
`md1dsp_a/b` (10 MiB); `mcf1/2_a/b` hold carrier configuration. NV/calibration
partitions are shared and must be preserved.

`ccci_mdinit` userspace participates in lifecycle, not IP packet transport.
SDK `mtk/package/system/ccci_mdinit/src/md_init_fsm.c:116–136` names
`/dev/ccci_monitor`, `/sys/kernel/ccci/boot`; its state machine uses CCCI ioctls.
`ccci_fsd` services modem filesystem requests through `/dev/ccci_fs`.
`nvram_daemon` prepares NV state before these start. The kernel does not replace
these functions merely because LK loaded the image.

## Control path: CCCI over CCIF, MIPC above it

- `eccci/mt6890/ccci_config.h:13,90–94`: generation 6297,
  `DATA_PLANE_DPMAIF`, `_DPMAIF_GEN98_CODA_`, `_DPMAIF_MED_SUPPORT_`.
- `eccci/inc/ccci_hif.h:14–39`: HIF ids CLDMA=0, CCIF=1, DPMAIF=2;
  modern generations select normal/control HIF=CCIF and network HIF=DPMAIF.
- `eccci/port/port_cfg.c:59–135`: filesystem, control/system and MIPC
  logical channels; `ttyCMIPC0…14` use `MD1_NORMAL_HIF` and char port operations.
  Their names do not mean physical UARTs or USB serial devices.
- `eccci/hif/ccci_hif_ccif.c:749` (`md_ccif_isr`), `:809–883`
  (`md_ccif_op_send_skb`), `:346–369`: shared-ring reads/writes and notifications;
  `:1223` requests the IRQ; `:1241` is `ccci_ccif_hif_init`.
- `eccci/port/port_char.c` and `port_proxy.c` dispatch char-device reads/writes,
  channel framing and received packets; `hif/ccci_ringbuf.c` implements rings.

**MIPC:** userspace message protocol/library over these CCCI character channels.
SDK `mtk/package/libs/mipc/lib/include/common/mipc_port.def:3–11` maps clients
to `/dev/ttyCMIPC*`; its Fibocom map must not be used as the Quectel assignment.
The SDK's `mipc.release.tar.gz` actually contains source, not just a `.so`:
`src/common/platform_linux.c:99,150,190,236,264` selects/opens the char ports and
reads/writes messages; `src/msg/msg_host.c` implements the receive/message path.
Archive location:
`sdk-fg360/release_sdk/mtk/prebuilt/modem/mt6890/evb6890v1_64_cpe_na/mipc.release.tar.gz`.
The OpenWrt recipe extracts it (`openwrt/package/mtk/libs/mipc/Makefile:37–60`).
It is vendor-restricted source; availability is not an open-source licence.

Fresh live descriptor evidence (no modem requests sent):

| Process | Open device |
|---|---|
| `ccci_mdinit` | `/dev/ccci_monitor` |
| `ccci_fsd` | `/dev/ccci_fs`, `/dev/ccci_md1_sta` |
| `ql_netd` | `/dev/ttyCMIPC11` |
| `mipc_submonitor` | `/dev/ttyCMIPC13`, `/dev/ccci_md1_sta` |
| `atcid` | `/dev/ttyCMIPC2` |

`ql_ril_service` had no PID at this snapshot, despite being in the startup list;
`nvram_daemon` also had none (expected for a one-shot), and `mtk_netagent` was
absent (intentionally not started). Do not infer that every configured service
must remain resident or that RIL can safely be deleted from startup.

## Packet path and interface creation

SDK source trace:

```text
ccmni.c: ccmni_init() → alloc/configure net_device → register_netdev()
IP transmit → CCMNI send callback → eccci/port/port_net.c:ccmni_send_pkt()
 → CCCI channel header / network port → HIF send_skb
 → ccci_hif_dpmaif.c:dpmaif_tx_send_skb() → DMA descriptors / hardware
DPMAIF IRQ → dpmaif_isr() → RX collection / dpmaif_rx_push
 → CCCI receive dispatch → port_net receive → ccmni_ops.rx_callback
 → Linux IP receive / GRO path
```

Exact anchors: `ccmni/ccmni.c:934,1676,1763,1850,2045–2065,2348`;
`eccci/port/port_net.c:235–305,316–373,433`;
`eccci/hif/ccci_hif.c:110–127`;
`eccci/hif/ccci_hif_dpmaif.c:1074,1360,2076,2152` (DMA mapping),
`:3263` (TX), `:3716` (ISR), `:4030–4054` (RX work/thread),
`:4242` (IRQ), `:5326–5382` (probe/match/registration).
Low-level hardware operations: `eccci/hif/dpmaif_drv.c`, `dpmaif_arch.h`,
`dpmaif_reg*.h`. MED/generation conditionals make register compatibility a real
porting question, even when another driver is also named DPMAIF.

Live `ccmni0…20` are already registered independently of a specific data call;
`mipc_wan_cli --data_call_act` activates a bearer and returns CID, interface and
IP parameters. The project's netifd handler validates those replies, brings the
returned ccmni interface up and publishes addresses/routes/DNS
([x28_mipc.sh lines 174–259](../../package/x28-mipc/files/x28_mipc.sh#L174)).
It does not implement the hardware driver or create a substitute WWAN transport.
SDK MIPC CLI source exists at
`mtk/package/network/utils/mipc-wan/src/mipc-wan-cli.c`; it uses message APIs
(e.g. lines 645–690 for AT-over-MIPC) and also has an alternative socket AT path.
This source is not proof of identical Quectel CLI semantics.

## Userspace, firmware and licence boundaries

| Component | Source / purpose | Status established by this audit |
|---|---|---|
| ECCCI, CCMNI, CCCI utilities | SDK kernel paths above; power, transport, network devices | GPL kernel source available locally; exact X28 vendor changes missing |
| `ccci_mdinit`, `ccci_fsd`, `libccci` | SDK `mtk/package/system/…`, `mtk/package/libs/libccci/src/ccci_lib.c` | Source exists; file headers restrict copying/use/disclosure; not established as freely redistributable |
| MIPC library | Archive source and `libmipc_msg.so` recipe | Source available locally with proprietary headers; exact Quectel version not established |
| `mipc_wan_cli` | SDK CLI source and stock binary | Source exists for sibling version; NOTICE alone does not license every linked vendor component |
| `libnvram`, `libfile_op`, NV services | Calibration/storage setup | Stock runtime dependency; full matching-source/licence closure unresolved |
| Quectel `ql_netd`, RIL, `libql_mipc`, `libql_at`, `libql_qlog` | Product-specific control/AT/backend | Stock binaries; matching Quectel source not established in this SDK |
| `libdtmf_detect`, `libmtk_audio_mixer_ctrl` | CLI/submonitor link closure | Stock binary dependencies recorded by inventory; not necessarily needed by a future minimal data stack |
| MD/DSP/DRDI, ATF and tinysys firmware | Boot partitions / prebuilt firmware | Binary firmware; no source or redistribution grant established |
| `x28-mipc`, `x28-modem`, LuCI protocol | This repository's `package/` | Public integration source; relies on vendor backend |
| `mt_wifi` | Stock Wi-Fi module | Declares Proprietary; upstream mt76 is a replacement candidate |

The exact stock ELF closure is documented in
[FIRMWARE-INVENTORY lines 79–96](../FIRMWARE-INVENTORY.md#L79), generated from
`private/firmware/inventory-rootfs_b.json`. Keep it distinct from an SDK source
licence audit. A `GPL` module declaration or source in an SDK is not evidence
that all userspace or firmware is open. Conversely, describing the entire
modem kernel stack as binary-only is contradicted by the local kernel sources.

Current bring-up order and file/mount/gadget dependencies are explicit in
[x28-modem.init lines 10–13, 23–98](../../package/x28-modem/files/x28-modem.init#L10).
Do **not** execute that script during investigation: it mounts writable vendor
data, starts services and sends `AT+CFUN=1`. `mtk_netagent` is intentionally
excluded because earlier tests found it changing CFUN. Legacy `router/`
`vendorbridge` and `vendorsync` proxy vendor HTTP/UI commands; they are not the
native modem transport. `experiments/` contains previous UI integration,
not a Linux 6.x modem implementation. The single dispatcher patch is a LuCI
routing fix, not a kernel forward-port.

## What remains unproven

The stock kernel's exact CCCI changes, full mandatory reset/NV service contract,
Quectel MIPC message/version differences, and optional acceleration/coexistence
dependencies need matching sources and offline comparison. No firmware reload,
modem reset, service removal, module loading, SIM change, suspend/resume or
traffic stress test was performed. Runtime binding/IRQ evidence establishes the
active transport without asserting that these untested lifecycle paths work.
