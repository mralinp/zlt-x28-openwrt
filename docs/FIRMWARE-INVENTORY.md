# Firmware inventory: kernel, modules, vendor packages

What the stock X28 firmware is made of, as groundwork for an OpenWrt build on the vendor kernel.
Tracks issue #19. Source: this unit's verified backup (2026-10-20, slot B), analysed offline with
[`tools/firmware/inventory.py`](../tools/firmware/inventory.py). Nothing from the device was run.

## Kernel

| | |
|---|---|
| Version | `Linux 4.19.205 (release@vm-mtk5g-96) … #0 SMP Fri Dec 22 12:10:12 UTC 2023`, OpenWrt GCC 7.5.0 `r0-f6109fc5` |
| Config | embedded (`CONFIG_IKCONFIG`), identical in `boot_a` and `boot_b`: [`firmware/kernel-4.19.205-x28.config`](firmware/kernel-4.19.205-x28.config), 1730 options |
| Modules | `CONFIG_MODVERSIONS=y`, `CONFIG_MODULE_SIG` off: a module must match this kernel's symbol CRCs, signatures are not checked |
| Firewall | **`CONFIG_NF_TABLES` not set**; iptables/ebtables only (also no `NET_DSA`; the switch uses `swconfig`) |
| Built-in cmdline | `console=ttyMT3,921600n1 …`, overridden by the bootloader (`CMDLINE_FROM_BOOTLOADER=y`, runtime `console=ttyS0,921600n1`) |

Extract again with:

```bash
python3 tools/firmware/inventory.py kconfig private/recovery/<backup>/images/mtd40-boot_b.bin out.config
```

## Kernel modules (146)

All carry `vermagic 4.19.205 SMP mod_unload modversions aarch64`.

- **91 netfilter modules, all iptables/ebtables** (`xt_*`, `ipt_*`, `ip6t_*`, `ebt_*`, `nf_conntrack*`, `nf_nat*`).
  **No `nf_tables`/`nft_*`.** OpenWrt 23.05's default `firewall4` needs nftables, so a port either
  builds nftables modules against this kernel (kernel source plus matching CRCs) or uses 23.05's
  iptables-based `firewall` (fw3) with the stock modules.
- **Vendor modules:** `mt_wifi` (13.7 MB, MT7915, the only module declaring `Proprietary`),
  `mtk_warp` + `mtk_warp_proxy` (Wi-Fi offload), `hw_nat`, `mapfilter`, `wifi_md_coex`,
  `conninfra`, `btmtk_uart`, `gps_drv`. Seven modules declare no licence at all (`mapfilter`,
  several `ebt_*`, `ts_bm`, `crc_ccitt`).

## Packages (346 installed, 112.4 MiB)

Architecture `aarch64_cortex-a55_neon-vfpv4` (339) plus `all` (7). Every ELF file belongs to an
installed package (the opkg file lists are intact).

**104 packages (78.5 MiB) are vendor code** (classified by package name and file ownership; not
yet checked against the OpenWrt 19.07 feed indexes). The rest are stock OpenWrt 19.07 packages.

| Group | Packages | Size | Largest |
|---|---|---|---|
| ZLT/Tozed | 9 | 30.5 MiB | `apptzporc` (28.5 MiB, 1070 files: web UI, `lan_mgr`, `sms_mgr`, `firewalltools`, `mini_httpd`, `devinfo`), `libtzproc`, `tzphone` |
| MediaTek Wi-Fi/mesh/network | 20 | 23.1 MiB | `kmod-mt_wifi`, `luci-app-wifi`, `kmod-warp`, `mapd`, `wapp`, `1905daemon`, `kmod-hw_nat` |
| MediaTek BT/GNSS | 9 | 15.9 MiB | `libmnl_gnss`, `bluedroid`, `mtk_agpsd`, `kmod-btmtk_uart`, `mnld` |
| MediaTek audio/voice | 8 | 3.5 MiB | `libmtk_audio_mixer_ctrl`, `libspeech_drv`, `libaudioparamparser` |
| MediaTek modem/cellular | 17 | 2.4 MiB | `redtea_mobile_sdk` (eSIM), `mtk_nvram`, `mipc-wan`, `mtk_netagent`, `ccci_*`, `mipc` |
| Quectel | 19 | 2.1 MiB | `ql-slic-sample`, `ql-ril-service`, `ql-netd`, `ql-slic`, `quectel_atcmd`, `libql_*` |
| MediaTek platform/boot/debug | 22 | 1.0 MiB | `mdlogger`, `aee`, `meta_tst`, `dconfig`, `thermal_core`, `dd-nand`; `preloader`/`lk`/`atf`/`sspm`/… own no rootfs files (flash images) |

The full per-file list (paths, sizes, owning package, module info) is in
`private/firmware/inventory-rootfs_b.json`. It is not committed because it names proprietary
files of this unit's firmware. Regenerate it with:

```bash
docker run --rm --network none -v x28-rootfs-b-analysis-20261021:/r:ro -v "$PWD/tools/firmware:/t:ro" \
  x28-firmware-tools:local python3 /t/inventory.py rootfs /r/rootfs > private/firmware/inventory-rootfs_b.json
```

## What a minimal router port needs (first cut)

| Function | Needed from the vendor layer | Notes |
|---|---|---|
| Cellular data | `ccci_mdinit`, `ccci_fsd`, `libccci`, `mtk_nvram`, `mipc`, `mipc-wan` (netifd proto), `mtk_netagent` | modem firmware is in `md1img_*`/`md1dsp_*` partitions, loaded via CCCI |
| Wi-Fi | `kmod-mt_wifi` (+ `mtk_warp_proxy`), `kmod-warp`, `datconf`; `wapp`/`mapd` only for EasyMesh | configured via `.dat` files, not mac80211 |
| Switch / LAN | `kmod-swconfig` (stock), `switch`, `mii_mgr` | no DSA in this kernel |
| Hardware NAT | `kmod-hw_nat`, `hwnat` | optional, for throughput |
| SMS / voice (project goal) | Quectel `ql-ril-*`, `ql-voice`, `ql-slic`, MediaTek audio packages | needed only for the voice/SMS phase |
| Likely droppable | BT/GNSS group, `redtea_mobile_sdk`, `sigma_*`, debug (`aee`, `mdlogger`, `meta_tst`, `mrdump_tool`), Tozed UI (`apptzporc`) | Tozed UI is what the native port replaces |

All of this is proprietary: a port reuses these binaries from the unit's own firmware (they
must match this kernel build) and must not redistribute them.

## Runtime dependencies (what actually starts and links)

From the enabled init scripts (`/etc/rc.d`, 48 services), the binaries each script calls, and
each binary's ELF `DT_NEEDED` closure (`inventory.py rootfs` records `needed`, `soname` and
`services`):

| Stage | Started by | Vendor packages in the closure |
|---|---|---|
| **Modem bring-up** | `S00` `0mount_all` (`ubiattach`/`ubimkvol`/`dd`/`mtd`), `1nvram_daemon`, `1restore`, `2ccci_fsd`, `3ccci_mdinit` | `mtk_nvram` (`libnvram`, `libfile_op`), `ccci_fsd`, `ccci_mdinit`, `libccci`: 4 packages, the rest stock |
| **Cellular data** | netifd protos `mipc.sh`/`ql_mipc.sh` → `mipc_wan_cli`, `mtk_netagent` (`S22`); `mipc_wan.init` (APN from SIM); `ql_netd`, `ql_ril_service` (`S85`); `mipc_submonitor` (`S99`) | `mipc` (`libmipc_msg`), `mipc-wan`, `mtk_netagent`, `libql_mipc`, `libql_at`, `libql_qlog`, **`libdtmf_detect`** (linked by `mipc_wan_cli`); `mipc_submonitor` also pulls `libmtk_audio_mixer_ctrl` |
| **Wi-Fi** | `/sbin/wifi` → `lib/wifi/mt7615e.lua` (`modprobe`, `iwpriv`, `brctl`, `hwnat`) | `kmod-mt_wifi`, `kmod-warp`, `datconf`, `hwnat`, **plus Tozed `lan_mgr` and `devinfo`**, which pull `libtzproc` (16 vendor libs) |
| **Switch** | `network` → `lib/network/switch.sh` (`swconfig`, `switch`) | `switch` only (stock libraries) |
| Tozed apps | `tzproc` (`S99`) starts ~20 services by script (`lan_mgr`, `sms_mgr`, `firewalltools`, `mini_httpd`, `wan_mgr`, `dialer`, …) | `apptzporc`, `libtzproc` |

Consequences for a port:
- Cellular data needs about 11 vendor packages, none of them Tozed. `ql_netd`/`ql_ril_service`
  serve the Tozed apps and may be droppable; to be confirmed on the device.
- The stock Wi-Fi script is tied to the Tozed apps (`lan_mgr`, `devinfo`). A port needs its own
  `mt_wifi` bring-up (`.dat` + `iwpriv`), not `mt7615e.lua` as shipped.
- The modem must be up before networking: the vendor runs its bring-up at `S00`, before `network` (`S20`).

## Firewall: OpenWrt 23.05 `firewall` (fw3, iptables) on this kernel

Checked against the kernel config and the 146 stock modules (`firewall4` is ruled out: no `nf_tables`):

| Needed by fw3 | Status |
|---|---|
| `ip_tables`/`ip6_tables`, `iptable_{filter,mangle,raw,nat}`, `ip6table_{filter,mangle,nat}` | modules present |
| `nf_conntrack` (IPv6 included since 4.19), `nf_nat`, `xt_conntrack`, `xt_comment`, `xt_multiport`, `xt_limit`, `xt_mac`, `xt_mark`, `xt_CT`, `xt_TCPMSS`, `xt_LOG`, `xt_time`, `xt_iprange` | modules present |
| MASQUERADE (`ipt_MASQUERADE`, `ip6t_MASQUERADE`), REJECT (`ipt_REJECT`, `ip6t_REJECT`, `nf_reject_ipv4/6`) | modules present |
| `ip6table_raw` | **missing** (`IP6_NF_RAW` not set): no IPv6 conntrack helpers or notrack rules |
| `xt_hashlimit` | **missing**: optional (fw3's SYN-flood rule uses `xt_limit`) |
| `nf_flow_table` / `xt_FLOWOFFLOAD` | **missing**: no software flow offloading; the vendor's `hw_nat` is the offload path |

**Verdict:** fw3 with iptables-legacy runs on the stock modules, with only the three gaps above.
The kernel also carries OpenWrt netfilter patches (`nf_conntrack_rtcache`). Not yet tested on
the device.
