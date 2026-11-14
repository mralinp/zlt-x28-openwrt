# Where the unit's RAM goes (#299)

Read-only measurements on the test unit (image 1.1.1, slot A, 5 min after boot, WAN up, no Wi-Fi client), 2026-11-14. No writes, no reboot.

## 1 GiB of physical RAM

`/proc/iomem`, `/sys/firmware/devicetree/base/reserved-memory` and `/sys/kernel/debug/memblock/{memory,reserved}`:

| MiB | What | How it is held |
|---:|---|---|
| 128.2 | Not System RAM: `md_smem_cache` 103.6 (`0x66000000`, `no-map`), ATF, ATF log, SSPM, MCUPM, MEDMCU, `md_smem_ncache` 5, `wocpu*` Wi-Fi offload, pstore, minirdump, log store | firmware carve-outs, fixed by the device tree |
| 895.8 | System RAM (`DMA32` present) | |
| 258.0 | `0x6de00000..0x7dffffff`, `md1rom` (256) plus 2 | in System RAM but reserved at boot (`memblock reserved`), never given to Linux |
| 32.5 | kernel image (`0x40080000..0x42100fff`) | reserved |
| 16.0 | CMA area (`0x65000000`, `CmaTotal` 16 MiB, `CmaFree` 0) | counted in `MemTotal`, all in use by drivers |
| about 20 | early allocations, `pl-drambuf`, `pl-boottag`, `aee-lk`, small memblock blocks | reserved |
| **628** | **`MemTotal`** (`managed` pages of the only zone, `DMA32`) | |

So of the 896 MiB the kernel sees, 268 MiB never reaches the allocator (`present` 896 minus `managed` 628). The two big ones are the modem ROM and the kernel image.

## What the 628 MiB holds

| MiB | Owner | Source |
|---:|---|---|
| 210.4 | free | `MemFree` |
| 52.9 | file cache and buffers | `Cached`, `Buffers` |
| 81.7 | slab (19.5 reclaimable; largest `kmalloc-2k` 25.9, `inode_cache` 10.5, `kmalloc-128` 9.5) | `Slab`, `/proc/slabinfo` |
| 56.3 | vmalloc, RAM-backed: `AdapterBlockAllocateMemory` 22.5 (`mt_wifi`), `load_module` 15.1, `wed_rx_bm_init` 7.0 (Wi-Fi offload), `ged_alloc` 5.4 (GPU), `_do_fork` 3.8 | `/proc/vmallocinfo` entries with `pages=` |
| 16.0 | CMA, fully used | `CmaTotal`, `CmaFree` 0 |
| 9.7 | programs, kernel stacks, page tables, percpu | `AnonPages`, `KernelStack`, `PageTables`, `Percpu` |
| **about 201** | **not attributed** | the remainder |

Not RAM, so not part of the above: `/proc/vmallocinfo` shows `ccci_map_phy_addr` 108.6 MiB, `paging_init` 32.5, `warp_cmd_process_msg` 4.1 as `phys=` (ioremap) mappings. They map the carve-outs and consume address space, not pages.

`dma_buf` has no objects, `ion` and the Mali GPU (`gpu_memory` 5 pages) hold almost nothing, and `ccmni`, `mt_wifi` and `mtk_warp` export no size parameters.

## What is not known

About 200 MiB of pages is held by something that is not slab, page cache, vmalloc or CMA. The likely owners are direct `alloc_pages`/`dma_alloc_coherent` pools of `mt_wifi`/`mtk_warp` (receive and DMA rings) and the modem network driver (`ccmni`, `ccci`). It cannot be split further here: `CONFIG_PAGE_OWNER` and `CONFIG_DEBUG_KMEMLEAK` are off, and `/sys/kernel/debug/page_owner` does not exist. The kernel command line is fixed by the bootloader.

## What can shrink

- **Fixed by hardware or firmware**: the 128 MiB carve-outs (device tree), `md1rom` 256 MiB (the modem image must stay in place while the modem runs; see #301), the kernel image.
- **Possible, not tried**: unload the Wi-Fi stack on a unit used without Wi-Fi (frees the `mt_wifi` and `wed` vmalloc, about 30 MiB, and its DMA pools, an unknown share of the 200 MiB); measure `MemFree` before and after. Needs a reboot-safe test on a unit that has a wired path, so it is a follow-up.
- **To measure the 200 MiB**: a kernel with `CONFIG_PAGE_OWNER=y` (our own kernel, #130), or compare `MemFree` across `rmmod mt_wifi` and `rmmod mtk_warp`.

## Commands

```bash
ssh x28 'grep -E "^(MemTotal|MemFree|MemAvailable|Buffers|Cached|Slab|SReclaimable|AnonPages|KernelStack|PageTables|Percpu|CmaTotal|CmaFree):" /proc/meminfo'
ssh x28 'grep "System RAM" /proc/iomem; cat /sys/kernel/debug/memblock/reserved'
ssh x28 'awk "/pages=/{for(i=1;i<=NF;i++)if(\$i~/^pages=/){split(\$i,a,\"=\");pg=a[2]};c=\$3;sub(/\\+0x.*/,\"\",c);s[c]+=pg*4/1024}END{for(k in s)printf \"%8.1f %s\\n\",s[k],k}" /proc/vmallocinfo | sort -rn'
ssh x28 'cd /sys/firmware/devicetree/base/reserved-memory; for d in */; do [ -f $d/reg ] && echo "$d $(hexdump -v -e "1/1 \"%02x\"" $d/reg)"; done'
```
