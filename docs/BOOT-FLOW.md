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
   **Confirmed by UART** ([uart-boot-log.md](research/uart-boot-log.md)): the bootloader prints
   `[QL_AB] ... slots[0].priority:14, slots[1].priority:15` and `ab_suffix: _b`.
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
`rootfs,pubk`, `rootfs,sigval` and `rootfs,hashvallist`. Each slot has a `rootfs_sig_*` partition. This establishes a signature-verification mechanism and rootfs metadata handoff; it does not by itself
establish that LK hashes the rootfs contents. A rootfs we build is not signed with the vendor key.

**Confirmed by UART**: on a normal boot LK prints `[SBC] ROOTFS_SIG_VFY Success` just before the kernel, after
verifying `boot_b` and the modem images; the preloader verifies `lk_b`, `tee_b` and the tinysys images. The log also
shows `sbc_en = 0`; the static failure path below is nevertheless fatal.

### LK failure path (offline analysis, 2026-10-28, #40)

**Observed bytes / decoded control flow:** the verified `mtd38-lk_b.bin` is 2 MiB,
SHA-256 `0ad94f065ebcfeefd157640d179b1b52779829a85179d07d38dd818b79007156`;
`mtd25-lk_a.bin` is byte-identical. All offsets below are **file offsets in the first LK payload**.
For that payload, virtual address = `0x84000000 + offset - 0x200`.
The ARM32 stub explicitly enters Thumb via `blx` at `0x3bc` targeting `0x277a`.
Thumb-2 `movw`/`movt` pairs independently corroborate the mapping: `0x286dc/0x286e4`
construct `0x840397d6`, pointing exactly at the cert1 string at `0x399d6`;
`0x28740/0x28748` construct `0x8403980f`, the Fail string at `0x39a0f`;
`0x28862/0x2886a` construct `0x840397f2`, the Success string at `0x399f2`.
These references require neither decompression nor an AArch64 interpretation. Later duplicate strings
were not used to infer the first payload's control flow.

| Site (file offset) | Decoded behavior |
|---|---|
| `0x3cea` | Calls the wrapper at `0x248c2` unconditionally in this local sequence. |
| `0x248c8–0x24908` | Initializes outputs and the `rootfs_sig` name (string `0x38f5e`), calls a suffix helper at `0x84cc`, then calls verifier `0x2856a` (`0x8402836a`). |
| `0x286ce–0x286ec` | Calls `0x2685e`; nonzero result is saved in `r6`, prints cert1 failure, branches to `0x28740`. Cryptographic internals of the callee were not audited. |
| `0x28740–0x2876a` | Prints Fail with error `r6`, clears both output words, frees allocated buffers. Earlier allocation-failure path prints Fail at `0x28708–0x28724` and joins the same return. |
| `0x2876e–0x28776` | Moves `r6` into return register `r0`, restores registers and returns. |
| `0x28830–0x2884e` | Further verification/export calls also branch to Fail on nonzero results. |
| `0x28858–0x28878` | Publishes output buffer/length, prints Success, sets `r6 = 0`, joins return. |
| `0x2490c–0x24930` | Compares verifier result to zero. Only equality stores outputs and returns normally. |
| `0x24932–0x24950` | Nonzero result calls `0x18b98` with assertion format (`0x2fe5a`), source path (`0x38f69`), line `0x30` (48), and expression `err == 0` (`0x34d0e`). |
| `0x18b98–0x18bc4` | Panic printer (prefix at `0x378d7`), then calls `0x8c5a` with `r0 = 0`, `r1 = 9`. |
| `0x8c5e–0x8c7e` | With `r0 = 0`, bypasses the alternate action calls, executes `cpsid i` at `0x8c7c`, then `b 0x8c7e` forever (`0x84008a7e`). |

**Inference from the traced path:** a reported rootfs-signature verification error **refuses to continue
booting**, by assertion/panic and an interrupt-disabled spin. It is neither log-only nor an immediate
A/B fallback. No SBC flag test, retry counter, slot write, or reboot occurs in the decoded wrapper-to-halt
path. This establishes behavior on a returned verification error, including cert1 failure; it does not
prove that every modified rootfs produces such an error. The exact signed content and cryptographic
callees remain unaudited. An independently running watchdog could subsequently reset the device;
reset-time slot policy remains unknown. No failure was induced on hardware.

### Kernel/userspace enforcement after handoff

**Observed:** LK's metadata exporter at `0x24954` uses the validated output buffer to set FDT properties:
`rootfs,pubk` via `0x249ac–0x249be`, `rootfs,hashvallist` via `0x24a10–0x24a22`
(string `0x38fb4`), and `rootfs,sigval` via `0x24a6e–0x24a7e`.
This is a handoff, not evidence of a kernel consumer.

A byte search of the complete 31,121,416-byte ARM64 `Image`
`private/firmware/20261021/boot-components/kernel.decompressed`
(SHA-256 `e1e2624d0146249e75fab5c36d51600aed978224622a56a02d8ba1f3301b2d47`)
found **none** of `rootfs,hashvallist`, `hashvallist`, `rootfs,pubk`, `rootfs,sigval`, or `rootfs_sig`.
Searching every regular-file member of the case-preserving stock archive
`private/firmware/20261021/rootfs-b-system.tar.gz` found no first-four strings either, including in the
archived modules. `rootfs_sig` occurs only in `etc/setup_link.sh` (partition links, lines 57–58,
83–84, 104), `lib/upgrade/platform.sh:43`, and `lib/upgrade/bootctrl.sh:31–32`
(partition-name constants). This archive excludes the writable overlay and user-data volumes;
see its private extraction README and [firmware inventory](FIRMWARE-INVENTORY.md).

**Unknown:** whether any kernel or userspace component enforces this metadata through indirect,
constructed, or otherwise unnamed access. Absence of literal names is not proof of absence of
verification. No consumer or enforcement path has been established. Consequently custom-rootfs
bootability remains unresolved; #40 is only partially answered.

To settle the remaining questions without modifying flash: obtain matching kernel/vendor source
and trace `/chosen` consumers and rootfs block reads; inspect stock upgrade handling of
`rootfs_sig_*` and slot success/failure records. A UART trace of a naturally occurring signature
failure (or an already available stock-upgrade failure capture) could corroborate the assertion
and any later watchdog/reset/slot behavior. A normal successful boot cannot establish failure policy.
No modified-image experiment is authorized or required by this analysis.

### Reproduce the disassembly

Use an existing Python environment with Capstone 5.0.7; no firmware code is executed:

```python
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
image = Path("private/recovery/20261020-capture-prepared-20261021/images/mtd38-lk_b.bin").read_bytes()
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
for start, end in [(0x248c2, 0x24954), (0x2856a, 0x2887e),
                   (0x18b98, 0x18bc8), (0x8c5a, 0x8c80)]:
    for insn in md.disasm(image[start:end], start):
        print(f"{insn.address:#010x}: {insn.mnemonic} {insn.op_str}")
```

The displayed addresses are file offsets; apply the mapping above for virtual addresses.

## Reproduce (offline, from the backup)

```bash
B=private/recovery/20261020-capture-prepared-20261021/images
cmp $B/mtd25-lk_a.bin $B/mtd38-lk_b.bin && echo identical
xxd -s 0x800 -l 32 $B/mtd03-misc.bin
strings -n 5 $B/mtd38-lk_b.bin | grep -E 'bootslot=|bootctrl|ql_raw_data|ROOTFS_SIG_VFY|rootfs,'
```

## Safe ways to settle the unknowns

- **UART** ([#2](https://github.com/mralinp/zlt-x28-openwrt/issues/2)): done for the read side, see
  [uart-boot-log.md](research/uart-boot-log.md). Still needed: a test of a modified image on slot A with a way back.
- **Vendor source or docs** ([#18](https://github.com/mralinp/zlt-x28-openwrt/issues/18)): the GPL request covers
  the kernel; the LK and Quectel boot-control behaviour may be documented by Quectel for the RG500L platform.
- **Vendor update path**: read-only inspection of the stock FOTA/upgrade scripts shows how the vendor itself
  switches slots and writes `rootfs_sig_*`.
