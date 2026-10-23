# Boot flow: A/B slots and rootfs signature

Read-only findings for [#3](https://github.com/mralinp/zlt-x28-openwrt/issues/3), from the live router (2026-10-23,
OEM 1.5.13) and the verified NAND backup ([RECOVERY.md](RECOVERY.md)). Nothing was written to the device.
What is **confirmed** and what is only **inferred** is marked; do not plan a flash on inferred items.

## Current slot

**Confirmed: slot B is active.** `/proc/cmdline` contains `bootslot=b` and mounts the root filesystem from
`ubi.mtd=42` (`rootfs_b`) as squashfs on `/dev/ubiblock0_0`. `lk_a` and `lk_b` are byte-identical in the backup.

```bash
ssh router 'cat /proc/cmdline; cat /proc/mtd'
```

## Partitions per slot

| Slot A (inactive) | Slot B (active) | Shared |
|---|---|---|
| `md1img_a` `md1dsp_a` `spmfw_a` `pi_img_a` `dpm_a` `medmcu_a` `sspm_a` `mcupm_a` | same with `_b` | `preloader` (+ backup), `proinfo`, `misc`, `para`, `expdb` |
| `lk_a` `tee_a` `boot_a` | same with `_b` | `nvcfg` `nvdata` `nvram` `protect1/2`, `seccfg`, `boot_para` |
| `rootfs_sig_a` `rootfs_a` `loader_ext_a` | same with `_b` | `mcf1/2_a/b`, `raw1` `raw2` `qraw`, `user_config`, `productinfo`, `user_data` |

## How the bootloader picks a slot

Three candidate controls were found. Which one actually decides is **not yet established**.

1. **MediaTek A/B record in `misc`** (inferred layout). Offset `0x800` holds a record with magic `00 41 42 30`
   (`"\0AB0"`), stored four times (`0x800`, `0x40800`, `0x80800`, `0xc0800`, one per erase block). After the
   magic and four `0xff` bytes, two 4-byte slot entries follow: A = `0e 00 01 00`, B = `0f 00 01 00`. Read as
   *priority, retries, successful*: A = 14/0/1, B = 15/0/1, so B wins, which matches the live slot.
2. **Quectel's own module** (confirmed present). LK contains `platform/mediatek/common/bootctrl/ql_raw_data_module.c`,
   the literal command-line fragments `bootslot=a` and `bootslot=b` (each next to its own root-device fragment),
   and answers the standard Android "set active slot" call with `set active slot: not supported!`. This points to
   Quectel's raw-data record, not the Android one, as the real selector.
3. **`qraw` record** (inferred meaning). `raw1` and `raw2` are empty; `qraw` has one small record, stored twice
   (`0x0`, `0x40000`), with a 32-bit value `2` at offset `0x0c`, a marker `AABB9876`, the module name `RG500L`
   and per-device MAC addresses (not reproduced here). `2` is the best candidate for "slot B".

**Unknown**: which of these LK reads, whether a failed boot falls back to the other slot (retry counting), and
what the vendor's FOTA path writes when it switches slots. `boot_para` holds data from `0x100000` that looks like
DRAM calibration; it is not shown to be slot-related.

## Rootfs signature check (blocker for custom images)

**Confirmed present**: LK contains `platform/mediatek/mt6890/sboot/rootfs_sig_vfy.c` with
`ROOTFS_SIG_VFY Success` / `ROOTFS_SIG_VFY Fail: %x`, and the running kernel's device tree `/chosen` node carries
`rootfs,pubk`, `rootfs,sigval` and `rootfs,hashvallist`. Each slot has a `rootfs_sig_*` partition. So the boot
chain checks a signature over the rootfs, and a rootfs we build is not signed with the vendor key.

**Unknown**: what a failed check does (refuse to boot, fall back, or only report), and whether the kernel or
userspace enforces `hashvallist`. Until that is known, flashing a custom rootfs to slot A cannot be planned.
Tracked in its own issue.

## Reproduce (offline, from the backup)

```bash
B=private/recovery/20261020-capture-prepared-20261021/images
cmp $B/mtd25-lk_a.bin $B/mtd38-lk_b.bin && echo identical
xxd -s 0x800 -l 32 $B/mtd03-misc.bin
strings -n 5 $B/mtd38-lk_b.bin | grep -E 'bootslot=|bootctrl|ql_raw_data|ROOTFS_SIG_VFY|rootfs,'
```

## Safe ways to settle the unknowns

- **UART** ([#2](https://github.com/mralinp/zlt-x28-openwrt/issues/2)): LK logs its slot and signature decisions
  at power-on; reading the log changes nothing.
- **Vendor source or docs** ([#18](https://github.com/mralinp/zlt-x28-openwrt/issues/18)): the GPL request covers
  the kernel; the LK and Quectel boot-control behaviour may be documented by Quectel for the RG500L platform.
- **Vendor update path**: read-only inspection of the stock FOTA/upgrade scripts shows how the vendor itself
  switches slots and writes `rootfs_sig_*`.
