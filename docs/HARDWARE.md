# Hardware: CPU, RAM, flash and trees

What the X28 has, what Linux gets, what uses it, and how its filesystem and device tree are laid out. Measured read-only on the test unit on 2026-10-31, on the native
image, about 2 h 50 min after boot with the LAN, Wi-Fi and 5G up. Run-time figures vary; the sizes do not.

| | |
|---|---|
| SoC | MediaTek MT6890 (T750), 4x Cortex-A55, aarch64 |
| CPU speed | 0.5 to 2.0 GHz, all four cores together, set by the `schedutil` governor |
| Modem | Quectel RG500L, on the SoC's own modem processor |
| Wi-Fi | MT7915, dual band |
| RAM | 1 GiB, of which Linux gets about 628 MiB |
| Flash | 1 GiB NAND, 51 partitions, of which OpenWrt gets about 288 MiB for installs and settings |

## CPU

The kernel's limits are 500 MHz and 2,000 MHz, in 16 steps, with one frequency shared by all four cores. It was running at
1.5 GHz when measured.

```bash
ssh router 'cd /sys/devices/system/cpu/cpufreq/policy0; cat cpuinfo_min_freq cpuinfo_max_freq scaling_cur_freq scaling_governor'
```

## RAM

The device tree's `memory` node gives 1 GiB at `0x40000000`. The modem has no RAM of its own, so it runs from this chip.
The bootloader reserves its share before Linux starts, and the split is fixed at boot, even if the modem is idle.

| Used for | MiB | Regions |
|---|---:|---|
| Modem firmware and its working memory | 256 | `md1rom` |
| Memory shared by modem and Linux | 109 | `md_smem_cache`, `md_smem_ncache` |
| Other firmware and helper processors | 24 | ATF, SSPM, MCUPM, MEDMCU, Wi-Fi offload (`wocpu`), logs and crash records |
| Kernel code and memory tables | about 7 | The remainder, not itemised |
| **Linux (`MemTotal`)** | **628** | |

The modem's share is not usable by Linux. How much of it the modem really uses cannot be seen from Linux.

What Linux's 628 MiB held at the time of measuring:

| Used for | MiB | From `/proc/meminfo` |
|---|---:|---|
| Free | 221 | `MemFree` |
| File cache, reclaimable when needed | 48 | `Cached` + `Buffers` |
| Kernel objects | 64 | `Slab`, of which 24 reclaimable |
| Programs | 5 | `AnonPages`. The largest process, `rpcd`, uses 2.4 MiB |
| Kernel stacks and page tables | 4 | `KernelStack`, `PageTables` |
| **Not itemised by the kernel** | **286** | The remainder, see below |

`MemAvailable` was 237 MiB. That is the number to watch, not `MemFree`.

**The 286 MiB is not explained.** It is memory taken directly by kernel code, which `/proc/meminfo` does not list; the
likely owners are the vendor Wi-Fi (`mt_wifi`, `mtk_warp`) and modem network drivers, but this has not been measured.
`VmallocUsed` (43 MiB) and the CMA pool (16 MiB) may overlap it. The programs are too small to be the cause of the
falling `MemAvailable` seen in the soak ([#149](https://github.com/mralinp/zlt-x28-openwrt/issues/149)).

`/tmp` is RAM. Its 313 MiB limit is a ceiling, not a reservation.

```bash
ssh router 'grep -E "^(MemTotal|MemFree|MemAvailable|Buffers|Cached|AnonPages|Slab|SReclaimable|KernelStack|PageTables|VmallocUsed|CmaTotal):" /proc/meminfo'
ssh router 'ls /proc/device-tree/reserved-memory/'
```

## Flash

The partitions total 1,022.5 MiB. A 1 GiB chip is inferred from that; the last 1.5 MiB is outside the partition table.

| Used for | MiB | Partitions |
|---|---:|---|
| Slot A | 198 | `rootfs_a` 64, `boot_a` 32, modem `md1img_a` 80 and `md1dsp_a` 10, bootloaders and small firmware 12 |
| Slot B | 198 | The same, holding stock firmware |
| Data area shared by both slots | 427.5 | `user_data`, see below |
| Modem calibration and settings | 112 | `nvcfg`, `nvdata`, `nvram`, `protect1`, `protect2` |
| Modem carrier configuration | 32 | `mcf1/2_a/b` |
| Crash logs | 20 | `expdb` |
| Boot and identity | 35.0 | `preloader` and backup, `proinfo`, `misc`, `para`, `seccfg`, `boot_para`, `loader_ext_a/b`, `raw1`, `raw2`, `qraw`, `user_config`, `productinfo` |

What OpenWrt uses:

| Mount | Size | Used | Free | On |
|---|---:|---:|---:|---|
| `/rom` (the image, read-only) | 7.8 MiB | 7.8 MiB | 0 | Volume `rootfs` in `rootfs_a` (30 MiB) |
| `/overlay` (installs and settings) | 287.6 MiB | 11.6 MiB | 271.3 MiB | Volume `data` in `user_data` |
| `rootfs_data` (fallback overlay) | 28 MiB | | | Second volume in `rootfs_a`, used if `data` does not mount |

`user_data` holds two UBI volumes: `data` (310 MiB, shared with stock's `/data`) and `customer` (100 MiB, stock's). Free
space on the overlay is also stock's free space, see [BUILD](BUILD.md).

Flash in slot B is reserved for stock today. The planned [recovery slot](https://github.com/mralinp/zlt-x28-openwrt/issues/152)
would keep its size but change what `rootfs_b` holds.

```bash
ssh router 'cat /proc/mtd; ubinfo -a; df -h'
```

## Root filesystem

`/` is an overlay: the read-only image with your changes on top. A file changed on `/` is stored in `/overlay/upper`.

```text
/                  overlay of /rom + /overlay
├── rom            the image, read-only SquashFS (7.8 MiB compressed)
├── overlay        installs and settings, UBIFS on user_data
├── bin sbin usr   programs
├── lib            libraries and kernel modules
├── etc            configuration
├── www            LuCI
├── root           root's home
├── vendor         vendor modem files
├── mnt
│   ├── vendor     modem calibration and settings: nvcfg, nvdata, nvram, protect_f, protect_s
│   └── data       stock's user_config
├── productinfo    unit identity data
├── tmp            RAM; var links here
├── dev proc sys   the kernel's virtual filesystems
└── config         the kernel's configfs
```

Kernel modules are the largest part of the image: about 21 MiB of about 39 MiB uncompressed.

| Where | Reboot | New image | Change it? |
|---|---|---|---|
| `/etc`, `/root`, installed packages (the overlay) | Kept | Starts fresh | Yes |
| `/tmp`, `/var` | Lost | Lost | Yes, it is RAM |
| `/rom` | Kept | Replaced | No, read-only |
| `/mnt/vendor`, `/productinfo`, `/mnt/data` | Kept | Kept | **No.** The unit's calibration and identity; the vendor stack uses them |

Reflashing byte-identical image bytes keeps the overlay, and the usual resets do not reach it, see
[RECOVERY](RECOVERY.md#clearing-settings-when-the-overlay-is-on-user_data-183).

```bash
ssh router 'ls -la /; cat /proc/mounts; du -sk /rom/*'
```

## Device tree

The bootloader passes the kernel this description of the hardware. It identifies the board as `Tozed,X28`, on MediaTek's
`evb6890v1_64_cpe_nand` reference design (`mediatek,mt6890`), and has about 326 top-level entries. Most are register blocks
of little use here.

| Node | What it is |
|---|---|
| `cpus` | The four cores; `opp-table0` holds the speed steps |
| `memory`, `reserved-memory` | RAM, and the [regions kept from Linux](#ram) |
| `nfi@11005000` | NAND controller (`mediatek,mt6880-nfc`) |
| `ethernet@15100000`, `gsw@0` | Ethernet (`mediatek,mt6890-eth`) and its switch (`mediatek,mt753x`) |
| `pcie@11280000`, `@11288000`, `@11290000`, `@11298000` | PCIe controllers |
| `wed@15010000`, `wed2@15011000`, `wocpu@15180000` | Wi-Fi offload |
| `mddriver`, `dpmaif@10014000`, `md_ccif*` | Modem driver and its links to Linux |
| `usb@11201000` | USB (`mediatek,mtu3`) |
| `serial@11002000`, `@11003000`, `@11004000` | UARTs |
| `lvts@1100b000`, `thermal-ntc1` to `4`, `thermal-zones` | Temperature sensors |
| `tz_gpio_keys`, `tz_gpio_leds` | Tozed's button and LED drivers |

A node does not prove a part is wired up. This tree comes from a reference design and still has nodes for parts such as a
display (`disp_*`) and GPU (`mali@13000000`), which this doc has not checked against the board.

The full tree is in [firmware/x28-device-tree.dts](firmware/x28-device-tree.dts), decompiled from `/sys/firmware/fdt`. The
parts specific to one unit are removed: `/chosen` (serial number, boot arguments), `/atag_rawdata_item` (MAC addresses) and
other MAC addresses. **Do not paste your own unfiltered tree into a public issue.** The command below prints only node
names and the board identity.

```bash
ssh router 'cd /proc/device-tree; ls; tr "\0" " " < compatible'
```
