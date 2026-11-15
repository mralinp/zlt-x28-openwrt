# Where the unit's RAM goes (#299)

Read-only measurements on the test unit (image 1.1.1, slot A, 5 min after boot, WAN up, no Wi-Fi client), 2026-11-14. No writes, no reboot.

## 1 GiB of physical RAM

`/proc/iomem`, `/sys/firmware/devicetree/base/reserved-memory` and `/sys/kernel/debug/memblock/{memory,reserved}`:

| MiB | What | How it is held |
|---:|---|---|
| 128.2 | Not System RAM: `md_smem_cache` 103.6 (`0x66000000`, `no-map`), ATF, ATF log, SSPM, MCUPM, MEDMCU, `md_smem_ncache` 5, `wocpu*` Wi-Fi offload, pstore, minirdump, log store | firmware carve-outs, fixed by the device tree |
| 895.8 | System RAM (`DMA32` present) | |
| 258.0 | `0x6de00000..0x7dffffff`, `md1rom` (256) plus 2 | counted as System RAM by the kernel (`memblock reserved`, `pfn_valid`) but absent from the linear map: a direct read faults (see "Probe of the 256 MiB") |
| 32.5 | kernel image (`0x40080000..0x42100fff`) | reserved |
| 16.0 | CMA area (`0x65000000`, `CmaTotal` 16 MiB, `CmaFree` 0) | counted in `MemTotal`, all in use by drivers |
| about 20 | early allocations, `pl-drambuf`, `pl-boottag`, `aee-lk`, small memblock blocks | reserved |
| **628** | **`MemTotal`** (`managed` pages of the only zone, `DMA32`) | |

So of the 896 MiB the kernel sees, 268 MiB never reaches the allocator (`present` 896 minus `managed` 628). The two big ones are the modem ROM and the kernel image.

## What the 628 MiB holds (before the Wi-Fi measurement below)

| MiB | Owner | Source |
|---:|---|---|
| 210.4 | free | `MemFree` |
| 52.9 | file cache and buffers | `Cached`, `Buffers` |
| 81.7 | slab (19.5 reclaimable; largest `kmalloc-2k` 25.9, `inode_cache` 10.5, `kmalloc-128` 9.5) | `Slab`, `/proc/slabinfo` |
| 56.3 | vmalloc, RAM-backed: `AdapterBlockAllocateMemory` 22.5 (`mt_wifi`), `load_module` 15.1, `wed_rx_bm_init` 7.0 (Wi-Fi offload), `ged_alloc` 5.4 (GPU), `_do_fork` 3.8 | `/proc/vmallocinfo` entries with `pages=` |
| 16.0 | CMA, fully used | `CmaTotal`, `CmaFree` 0 |
| 9.7 | programs, kernel stacks, page tables, percpu | `AnonPages`, `KernelStack`, `PageTables`, `Percpu` |
| **about 201** | **not attributed**; about 140 of it is the two Wi-Fi radios (Measurements) | the remainder |

Not RAM, so not part of the above: `/proc/vmallocinfo` shows `ccci_map_phy_addr` 108.6 MiB, `paging_init` 32.5, `warp_cmd_process_msg` 4.1 as `phys=` (ioremap) mappings. They map the carve-outs and consume address space, not pages.

`dma_buf` has no objects, `ion` and the Mali GPU (`gpu_memory` 5 pages) hold almost nothing, and `ccmni`, `mt_wifi` and `mtk_warp` export no size parameters.

## Measurements (2026-11-14, #299 and #301)

**Wi-Fi interfaces hold most of the unattributed RAM.** On the test unit (image 1.1.1, WAN up), `MemFree` with `ip link set <if> down/up`, settled 6 s or more:

| State | `MemFree` MiB | Difference |
|---|---:|---:|
| both radios up (`ra0` 2.4 GHz, `rai0` 5 GHz) | 208.6 | |
| `rai0` down | 279.0 | +70.4 |
| `ra0` and `rai0` down (`wifi down`) | 348.3 | +139.7 |
| `ra0` up only | 279.1 | +70.5 |

Each radio interface holds about 70 MiB while it is up, 140 MiB for both: 22% of Linux's 628 MiB and about 70% of the previously unattributed 200 MiB. `VmallocUsed` falls by about 7 MiB (`wed_rx_bm_init`); the rest is page allocations (descriptor and buffer rings of the vendor `mt_wifi` and `mtk_warp`), invisible in `/proc/meminfo`. With Wi-Fi off the unit reaches `MemAvailable` 367 MiB. The modules stayed loaded (unloading them on the only test unit risks a crash for a few MiB).

**The modem's 256 MiB is requested by the modem firmware, not by the device tree.** `md1img_a` (an 80 MiB partition) holds the MOLY image `MT6890_EVB_QUECTEL_1907MP1_RG500L_MDBIN_PCB01_MT6890_S00.MOLY_NR15_R3_MD700_MP_V53_5_P98.bin` (build 2023/12/20, Quectel RG500L). Parsed with the MediaTek image header (magic `0x58881688`):

| Section | Size |
|---|---:|
| `md1rom` | 29.07 MiB |
| `md1drdi` | 2.92 MiB |
| certificates | about 7 KiB |
| rest of the partition | empty (`0xff`), data ends at 32 MiB |

Its `CHECK_HEADER` (version 6, at the end of `md1rom`, offset `0x1d10d80`) carries `0x10000000` at `+0xac`: 256 MiB, the size of `md1rom` in the device tree. Other fields hold 245 MiB and 11 MiB (sum 256) and sizes near the shared memory (`0x6520000` = 101.1 MiB; the DT block is 103.6 MiB). The field meanings are inferred from the layout of the vendor `md_check_header` structure; only the 256 MiB value is matched to a device-tree region, the others are not confirmed. The image is 32 MiB, so about 224 MiB of the 256 is the modem's heap and working memory, which the modem firmware itself declares.

**Reading.** LK builds `md1rom` and the shared-memory blocks from what this modem firmware asks for. They cannot be shrunk from Linux, the device tree or the AP side alone; they need a modem firmware build with a smaller layout, which only the modem vendor (Quectel, MediaTek) can make. The Wi-Fi driver's 140 MiB is the part the project can change.

**Probe of the 256 MiB (test unit, 2026-11-15, #301).** Whether the modem touches more than its 32 MiB image is not measured, because Linux cannot read the region:

- `/dev/mem` is blocked (`CONFIG_STRICT_DEVMEM=y`) and `/proc/kcore` is not built.
- A small read-only module reading the linear-map address of `0x6de00000` took a translation fault (`scan_init`, `do_translation_fault`); the kernel panicked and the unit rebooted by itself (one unplanned reboot; it came back normally on slot A).
- Mapping the range with `__ioremap` is refused (`WARN_ON(pfn_valid(...))`, returns NULL): the kernel counts it as RAM, yet it has no mapping. Nothing was read.
- A read would need a hand-built mapping (`vmap` with explicit page protection), with reboot risk, or the modem vendor's tooling, or JTAG/UART. Until then, "224 MiB is heap and working memory" stays an inference from the header.

Method note: a freestanding module (no kernel headers) builds on macOS with `clang -target aarch64-linux-gnu -ffreestanding -mgeneral-regs-only -fno-pic -fno-asynchronous-unwind-tables`. The module header (`.gnu.linkonce.this_module`, 0x380 bytes, `init` at 0x170, `exit` at 0x318), the `.plt`, `.init.plt` and `.text.ftrace_trampoline` stubs, the `vermagic` string and the CRCs of `module_layout`, `printk`, `memstart_addr` and `__ioremap` were copied from the unit's own stock modules (`__versions`), because the SDK kernel tree is 4.19.190 and the unit runs 4.19.205. It loaded and ran on the unit; only the memory access was wrong.

## What can shrink

- **Wi-Fi driver pools, about 140 MiB**: the vendor `mt_wifi` and `mtk_warp` allocate about 70 MiB per radio and export no size parameter. An open driver sizes its rings itself: upstream `mt76` supports the MT7915 (`mt7915e`). Whether this board's Wi-Fi attaches the way `mt7915e` expects, and whether the WED offload needs the vendor `mtk_warp`, is untested. This is the lever for the v2 firmware and for the open-source driver goal.
- **Fixed by the modem firmware**: `md1rom` 256 MiB and the shared memory about 104 MiB (see above), the 128 MiB of firmware carve-outs, the kernel image, the 16 MiB CMA (used by drivers).
- **About 60 MiB** of Linux memory is still unattributed (the modem network driver `ccmni`/`ccci` and others). Measure it the same way on a spare unit, or with `CONFIG_PAGE_OWNER` on our own kernel (#130).

## Commands

```bash
ssh x28 'grep -E "^(MemTotal|MemFree|MemAvailable|Buffers|Cached|Slab|SReclaimable|AnonPages|KernelStack|PageTables|Percpu|CmaTotal|CmaFree):" /proc/meminfo'
ssh x28 'grep "System RAM" /proc/iomem; cat /sys/kernel/debug/memblock/reserved'
ssh x28 'awk "/pages=/{for(i=1;i<=NF;i++)if(\$i~/^pages=/){split(\$i,a,\"=\");pg=a[2]};c=\$3;sub(/\\+0x.*/,\"\",c);s[c]+=pg*4/1024}END{for(k in s)printf \"%8.1f %s\\n\",s[k],k}" /proc/vmallocinfo | sort -rn'
ssh x28 'cd /sys/firmware/devicetree/base/reserved-memory; for d in */; do [ -f $d/reg ] && echo "$d $(hexdump -v -e "1/1 \"%02x\"" $d/reg)"; done'
ssh x28 'ip link set rai0 down; ip link set ra0 down; sleep 6; grep -E "^(MemFree|MemAvailable):" /proc/meminfo; wifi reload'   # Wi-Fi off: +140 MiB; wifi reload restores both radios
ssh x28 'dd if=/dev/mtd17ro bs=1M 2>/dev/null' > md1img_a.bin   # read-only; parse the image headers (magic 88 16 88 58) and CHECK_HEADER
```
