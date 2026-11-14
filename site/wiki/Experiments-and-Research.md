# Experiments and research

What we tried, what we learned, and what we dropped. Notes in
[`docs/research/`](https://github.com/mralinp/zlt-x28-openwrt/tree/main/docs/research) are point-in-time records; the pages of
this wiki give the current state.

## Dropped or superseded

| Experiment | Outcome | Why |
|---|---|---|
| <a id="stage-1-the-stock-firmware-overlay"></a>**Stock-firmware overlay** (`router/`): `vendorbridge`, `vendorsync`, `voicectl` | worked, superseded | it adapted UCI to the vendor backend; the goal was a real OpenWrt. SMS worked there; voice was blocked by the SIM |
| **Recovery slot on B** (#152, #153) | dropped | only `rootfs_b` (64 MiB) is plain data; not worth losing the automatic fall-back ([slot-b-reuse](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/slot-b-reuse.md)) |
| **Rust flasher `x28flash`** (#270) | dropped | the Python flasher as one PyInstaller binary won; the note is kept for its protocol and download-agent findings ([rust-flasher-design](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/rust-flasher-design.md)) |
| **Writing `misc` over USB** | failed twice, on two units | the download agent never acknowledges the first block. `misc` is written live only |
| **Official `kmod-*` packages** | cannot work | 5.15 modules on a 4.19 `MODVERSIONS` kernel. Replaced by the stub and built-module feed |
| **`mtk_netagent` for IPv6** | not used | it forces the radio off in our start order |
| **GPL source request** to ZLT/Tozed (#18) | no source obtained | a sibling-device SDK arrived later and is used privately |
| **Upstream `mt76` for Wi-Fi** | not evaluated | the vendor `mt_wifi` driver is what runs |

## Parked

| Topic | State | Note |
|---|---|---|
| Own 4.19 kernel from the sibling SDK (#130) | not tried | would unlock nftables, namespaces and more kmods; a flash with brick risk |
| Mainline kernel ("v2", #546) | feasibility and a roadmap written; on a branch: an OpenWrt 25.12 build environment and serial-only Linux 6.12 boot artifacts, with the LK device-tree handoff and the preloader traced. Nothing booted on a unit | [feasibility](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/x28-mainline-kernel-feasibility.md), [roadmap](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/x28-mainline-roadmap.md) |
| Patching LK's boot authentication | previewed in Ghidra only; no patch made | [lk-boot-auth-preview](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/lk-boot-auth-preview.md) |
| Fan control from LuCI (#47) | blocked on hardware | no fan header on the board |
| USB Ethernet (NCM) to a computer (#488) | works with a patched module, not shipped | the unpatched vendor code panics the kernel |
| ADB on the USB port | not planned | probably inert on retail firmware |
| IPv4 passthrough (#543) | guarded experiment in v1.1.0 | no document yet |
| Voice calls (#16, #17) | IMS registers and calls connect, but no voice bearer and no audio; a support request to Quectel is drafted | [Cellular and telephony](Cellular-and-Telephony.md#voice-calls-connect-but-no-audio) |

## Findings worth keeping

**Boot and security**

- Secure boot, SLA and DAA are off. LK checks `rootfs_sig` metadata, not rootfs content; a custom rootfs boots.
  [rootfs-signed-content](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/rootfs-signed-content.md),
  [content-enforcement](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/content-enforcement.md),
  [lk-authentication-ghidra](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/lk-authentication-ghidra.md)
- The preloader picks the slot from `misc`, counts tries, switches at 6.
  [slot-selection](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/slot-selection.md),
  [uart-boot-log](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/uart-boot-log.md)
- No layer of the boot chain wipes flash on a reset-button press.
  [reset-wps-buttons](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/reset-wps-buttons.md)

**Flash writes, in the order they were proven**

[first-write-plan](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/first-write-plan.md) →
[patched-identical-write-result](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/patched-identical-write-result.md) →
[changed-page-restore-result](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/changed-page-restore-result.md) →
[recovery-route-proof](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/recovery-route-proof.md) →
[rootfs-a-write-plan](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/rootfs-a-write-plan.md)

**Kernel modules**

- Modules built without symbol CRCs load on the `MODVERSIONS` kernel.
  [kernel-module-crc](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/kernel-module-crc.md)
- All 976 official kmods sorted by what it takes to run them.
  [kmod-gap](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/kmod-gap.md)
- The vendor kernel has the 5.x crypto library, so five ChaCha/Poly1305 modules come from the SDK's own files.

**Hardware and modem**

- The modem is a subsystem of the SoC, reached over CCIF, DPMAIF and `ccmni`.
  [x28-hardware-architecture](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/x28-hardware-architecture.md),
  [x28-modem-driver-analysis](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/x28-modem-driver-analysis.md)
- The stock firmware's operator (SIM) lock.
  [operator-lock](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/operator-lock.md)
- Flashing a second unit with no UART and no SSH; the PRO runs a newer stock userspace (Quectel 2024-01-15).
  [flash-other-units](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/flash-other-units.md)

**Measurements**

| Measured | Result |
|---|---|
| Idle SoC temperature | 65 °C stock, 46 °C stock with a fan, about 40 °C native |
| WireGuard | 715 Mbit/s send, 330 receive |
| OpenVPN | about 100 Mbit/s, one core |
| Passwall2 from a LAN client | 206 / 40 Mbit/s |
| xray cost | 0.45 cores per 100 Mbit/s |
| Soak | 26.6 h, no unexplained restart |
| Boot to DHCP on the PRO | 34 s with the guard |

## Design notes behind shipped features

[sysupgrade-design](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/sysupgrade-design.md) ·
[overlay-policy](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/overlay-policy.md) ·
[signed-package-feed](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/signed-package-feed.md) ·
[vendor-ipset-packaging](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/vendor-ipset-packaging.md) ·
[x28-flasher-binary](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/x28-flasher-binary.md) ·
[native-image-readiness](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/native-image-readiness.md)

## Legacy documents

Stock-firmware era, kept for history:
[vendor-command-map](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/vendor-command-map.md),
[luci-on-stock](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/luci-on-stock.md),
[DEVICE-AUDIT](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/DEVICE-AUDIT.md),
[archive/](https://github.com/mralinp/zlt-x28-openwrt/tree/main/docs/archive).
