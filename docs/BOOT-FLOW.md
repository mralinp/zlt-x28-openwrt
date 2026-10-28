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
   and answers the standard Android "set active slot" call with `set active slot: not supported!`. This establishes
   a vendor boot-control implementation, but does not establish which record it uses; the stock upgrade
   scripts below write the `misc` record.
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

**Further offline kernel inspection (#40):** this Image has uncompressed, base-relative kallsyms
(`CONFIG_KALLSYMS_UNCOMPRESSED=y`, `CONFIG_KALLSYMS_BASE_RELATIVE=y`). The 124,436-entry
32-bit offset table occupies `[0xef7800, 0xf71050)`; the 64-bit count at `0xf71200` is 124,436.
Length-prefixed names occupy `[0xf71300, 0x122ca78)`. Pairing these gives `_text = 0`,
`_stext = 0x800`, and the following function offsets. All kernel locations here are offsets in the
**decompressed Image**, not in the compressed `boot_b` partition or virtual addresses.

| Decoded function range (end exclusive) | Relevant instruction(s) |
|---|---|
| `squashfs_read_data` `[0x2da65c, 0x2dabec)` | Calls `ll_rw_block` at `0x2da7f0` and `squashfs_decompress` at `0x2da820`. |
| `ubiblock_do_work` `[0x76cb68, 0x76cc4c)` | Calls `ubi_leb_read_sg` at `0x76cc30`; a negative return branches to request completion at `0x76cc38`. |
| `ubi_leb_read_sg` `[0x75e690, 0x75e7b8)` | Calls `ubi_eba_read_leb_sg` at `0x75e774`. |
| `ubi_eba_read_leb_sg` `[0x75ff74, 0x760104)` | Calls `ubi_eba_read_leb` at `0x76007c`. |
| `ubi_eba_read_leb` `[0x75f9d0, 0x75ff74)` | Calls `ubi_io_read` at `0x75fe48`; also contains a `crc32_le` call at `0x75ff0c`. |
| `ubi_io_read` `[0x761fec, 0x76253c)` | Calls `mtd_read` at `0x7621fc`. |

**Bounded inference:** these six fully decoded function bodies contain no hash-list comparison,
cryptographic verification call, or indirect `blr` call. Their block reads, error handling,
and decompression do not establish rootfs-signature enforcement. The CRC32 call is not evidence
of signature verification. This audit does not cover the whole kernel: `_mcount` instrumentation
calls, other callees, lower-level MTD/NAND drivers, initialization, and other read paths remain
outside this inspection. The recorded boot command line selects `/dev/ubiblock0_0` directly,
not a device-mapper root ([UART log](research/uart-boot-log.md)); that observation also cannot rule
out vendor enforcement elsewhere.

**Lower-level callback inspection:** `mtd_read` (`0x740ccc`) loads its read callback from
object offset `0x90` at `0x740d20`, calls it at `0x740d3c`, and returns through ECC/error handling.
`allocate_partition` installs `part_read` (`0x74355c`) at `0x743dec–0x743df4` when the parent has
that callback. `part_read` adds the partition offset, loads the parent's callback at `0x7435a8`,
and calls it at `0x7435b4`. Separately, vendor `nand_probe` installs `nand_read` (`0x77a0d8`)
at object offset `0x90` at `0x77b498–0x77b4a0`. These are observed setup assignments, not runtime
proof that no callback is subsequently replaced.

This vendor `nand_read` calls `nand_operation` at `0x77a12c` with `w6 = 1` (read).
`nand_operation` selects `nandx_read` (`0x76f6cc`) at `0x779a40–0x779a64` for that argument;
its three indirect operation calls use that selection. `nandx_read` reaches additional lower-level
operations, including an indirect call at `0x76f974`; that layer is not resolved here.
No hash-list verification was identified in these inspected wrapper bodies.

The common `_mcount` entry at `0x1e4a0` loads `ftrace_trace_function` (symbol offset `0x1b8daa0`)
at `0x1e4a8–0x1e4ac`, skips the callback if it equals `ftrace_stub` (`0x1e4d8`, a `ret`), and otherwise
calls it at `0x1e4cc`. Thus the instrumentation call is an actual indirect boundary; its runtime
target cannot be inferred from this static Image. Lower-level callbacks, instrumentation state,
and other paths remain explicit limits of the negative result.

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

### Stock upgrade and boot-completion path (#40)

**Observed script content, not executed:** in the same stock filesystem archive, `lib/upgrade/platform.sh`
lines 19–20 name `root_ro*.sig` and `*.squashfs` separately. `lib/upgrade/bootctrl.sh` writes them to the
opposite slot at lines 401–402 (current A) or 429–430 (current B). It clones partitions missing from the
update at lines 407/435 (`clone_non_update_images`, lines 351–371), then changes slot metadata at line 446.
For current B, `change_slot_info` lines 223–242 request A priority 15, retry 3, success 0 and B priority 14;
these are the call-site arguments, not a verified runtime write result. NAND metadata writes target `misc`
offset `0x808` and the three copies spaced `0x40000` apart (lines 92–98). This corroborates the
priority/retry/success field interpretation above; it does not establish bootloader retry policy.

**Recovery implication:** the archive includes `etc/rc.d/S99zmtk_boot_done` pointing to
`../init.d/zmtk_boot_done`. Its `boot()` calls `check_bootctrl` at line 110. If NAND is selected and the
current slot is not marked successful, the script calls `ab_image_sync` for the other slot (lines 22–59
for current A; 60–99 for current B) before recording success. `ab_image_sync` (`bootctrl.sh:275–292`)
iterates the destination slot's partition list, including `rootfs_sig` and `rootfs` (lines 38–39).
`clone_image_adapter` reads the opposite slot and writes the destination with `mtd` at line 335;
NAND preloader cloning is skipped. There is also a restore branch when the other slot's retry byte
exceeds 3 (`zmtk_boot_done:124–141`). **Do not assume the other slot stays an untouched recovery copy
after a stock upgrade reaches userspace.** These conditions were established by reading scripts;
they were not triggered or tested on the router.

Neither this upgrade path nor this boot-completion script reads `hashvallist` or verifies its hashes.
Marking a boot successful here is not evidence of rootfs-content verification. These scripts must
not be sourced or invoked as read-only probes: even their metadata getters write temporary files,
and the completion/upgrade paths write partitions.

Archive-member SHA-256 for reproducing line references:

- `lib/upgrade/platform.sh`: `9fd775f27bb762b26a6f12540f62e76ab2cece3bc85b33d19dd5f1ffd777f340`
- `lib/upgrade/bootctrl.sh`: `36a59e5ec91e6fc961f3e05ba809b7079a282a5a0801a7b1ad0895df849de7bd`
- `etc/init.d/zmtk_boot_done`: `2549dedeeb89f1c0ca1a340abea5f69f3ed0b7572c0a56a77138bfc7e8822812`

### Reproduce the kernel and script inspection

Read archive members with Python `tarfile.extractfile`; no extraction or script execution is needed.
For example, print `rootfs/etc/init.d/zmtk_boot_done` with line numbers. For the kernel, use the same
Capstone environment and Image identity above:

```python
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
image = Path("private/firmware/20261021/boot-components/kernel.decompressed").read_bytes()
count = struct.unpack_from("<Q", image, 0xf71200)[0]
assert count == 124436
offsets = struct.unpack_from(f"<{count}I", image, 0xef7800)
assert list(offsets) == sorted(offsets)
names, pos = [], 0xf71300
for _ in range(count):
    size = image[pos]
    names.append(image[pos + 1:pos + 1 + size].decode())
    pos += size + 1
assert pos == 0x122ca78
symbols = {name[1:]: offset for name, offset in zip(names, offsets)}
assert symbols["_text"] == 0 and symbols["_stext"] == 0x800
md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
start = symbols["ubiblock_do_work"]
end = next(offset for offset in offsets if offset > start)
insns = list(md.disasm(image[start:end], start))
assert sum(insn.size for insn in insns) == end - start
for insn in insns:
    print(f"{insn.address:#010x}: {insn.mnemonic} {insn.op_str}")
```

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
