# Native-image input and boot audit (#74)

Offline review on 2026-10-29, after the [bounded recovery PASS](changed-page-restore-result.md).
**No existing build artifact is ready to flash to the X28.** Recovery testing is complete for that
scope; the next implementation is local image assembly plus a safe first-A boot plan. No router
access, firmware/helper execution, slot change, flash write or reboot occurred during this audit.
The supplied SDK was not treated as compatible firmware; its generic UBI header was consulted only
for format constants, not board/modem compatibility.

## Verified inputs and artifact classification

All nine present outputs named by `private/build/out/sha256sums` match that local manifest. The
userspace tarball is 4,730,633 bytes, SHA-256
`f78736ded5c9c9961f2119f98221b1a5d23d7faa409728c4961b5fea47d378e2`.
These checks establish integrity against the recorded build outputs, not a new vendor authenticity claim.
Below, names share prefix `openwrt-23.05.5-armsr-armv8-generic-`.

| Existing output | Actual content / measured size | X28 use |
|---|---|---|
| `rootfs.tar.gz` | file tree, 177 packages, 100 `.ko` files under `lib/modules/5.15.167` | userspace assembly input; not a NAND image |
| `kernel.bin` | raw ARM64 Image, 16,515,584 bytes; embedded banner `Linux version 5.15.167` | exclude from the first stock-kernel candidate |
| `squashfs-rootfs.img.gz` | raw SquashFS at decoded offset 0; decoded file 109,051,904 bytes (104 MiB), no UBI wrapper | too large for the 64 MiB target as supplied; not the target format |
| `ext4-rootfs.img.gz` | ext4 magic `53 ef` at decoded offset 1080; decoded file 104 MiB | not stock UBI/SquashFS and too large as supplied |
| `*-combined.img.gz` | decoded gzip member 243,564,032 bytes; MBR signature `55 aa` at offset 510; 532 trailing bytes after gzip member | generic disk image, not the NAND partition format |

The gzip members were fully decoded with checksum validation; appended combined-image bytes were
counted, not executed or interpreted as firmware. A naive whole-file `gzip.read()` rejects those
trailing bytes, so it is not the right way to determine the combined member's decoded size.
The separate cpio archive and `profiles.json` also passed local manifest hashes; neither is an X28
flash image. Renaming any of these files or changing its extension cannot supply the missing layout.

## Preserve this unit's boot/kernel; replace incompatible modules

The verified `mtd27-boot_a.bin` and `mtd40-boot_b.bin` are byte-identical, 32 MiB, SHA-256
`c8cc8244078cb6539c72842540250bc7ca40b8fb9b66123a6bd85a529e47b120`.
At boot-partition file offset 0 is `ANDROID!`; little-endian fields give kernel size 9,017,297
at `0x08`, load address `0x40080000` at `0x0c`, zero ramdisk size at `0x10`, page size 2048 at
`0x24`, and header version 2 at `0x28`. The gzip payload begins at `0x800`.
The decompressed kernel is 31,121,416 bytes, SHA-256
`e1e2624d0146249e75fab5c36d51600aed978224622a56a02d8ba1f3301b2d47`, banner `Linux version 4.19.205`.
Keeping the complete stock boot partition avoids inventing an unverified boot/DTB repacking procedure.

The stock system archive contains **146** 4.19.205 modules; the new userspace archive contains
**100** 5.15.167 modules. Example embedded vermagic strings:

- stock `lib/modules/4.19.205/iptable_nat.ko`: `4.19.205 SMP mod_unload modversions aarch64`;
- new `lib/modules/5.15.167/aquantia.ko`: `5.15.167 SMP mod_unload aarch64`.

Package databases separately contain 72 stock versus 86 new `kmod-*` packages; package counts are
not module-file counts. Their `kernel` package versions are respectively
`4.19.205-1-90675086d7e6b2794a570b6bcb152103` and
`5.15.167-1-d93c06fec09a43c065e8a5f8151bb87f`.
An assembler must replace module files, autoload configuration **and** incompatible package records;
retaining 5.15 package metadata while copying 4.19 files is not a complete integration.

The new tarball lacks `nvram_daemon`, `ccci_fsd`, `ccci_mdinit`, `ql_netd`, `ql_ril_service` and the
stock bring-up scripts. The [earlier ABI/runtime checks](../TESTING.md#17-the-2305-userspace-runs-on-the-x28-ram-chroot-stock-kernel)
prove a useful userspace baseline; they do not prove the assembled init/network/modem/Wi-Fi stack.
Vendor files, four compatibility libraries, firmware and module dependencies must be selected from
this unit's own stock inputs; blindly copying every stock init script is unsafe.

## Actual slot-A UBI layout and capacity

Both original 64 MiB `rootfs_a` and `rootfs_b` captures were independently walked by PEB. EC/VID
and the first two volume-table record CRCs passed; the two layout copies agree in each slot.
Offsets below are **partition-relative**, not absolute NAND addresses.

| Field | Observed value |
|---|---|
| PEB / main-data partition size | `0x40000` / `0x4000000` bytes (256 PEBs) |
| VID header / data offsets | `0x1000` / `0x2000` within each EC block |
| LEB data capacity | `0x3e000` = 253,952 bytes |
| Layout-copy PEB offsets | `0x1f80000`, `0x1fc0000`; records start `+0x2000` |
| Volume 0 | `rootfs`, type 1 (dynamic), 124 reserved PEBs, alignment 1, data pad 0, flags 0 |
| Volume 1 | `rootfs_data`, type 1, 116 reserved PEBs, alignment 1, data pad 0, flags 0 |
| Current rootfs-volume capacity | 31,490,048 bytes; the 64 MiB whole-partition limit is not this volume's limit |
| Stock SquashFS | magic `hsqs`, block size 262,144, compression ID 4 (XZ), `bytes_used` 31,274,410 |

For reproduction, EC offsets `0x10/0x14` hold big-endian VID/data offsets; VID offsets `0x08/0x0c`
hold volume ID/logical block number. Volume records are 172 bytes: reserved PEBs at `+0`, type at
`+12`, name length at `+14`, name at `+16`, flags at `+144`, CRC at `+168`. CRC checks use the
stored big-endian value against `(zlib.crc32(header_without_crc) ^ 0xffffffff) & 0xffffffff`.
Reconstruct volume 0 in logical-block order as in the [signed-content reproduction](rootfs-signed-content.md#reproduce-the-content-match-offline).

Both slots reconstruct the same signed SquashFS digest, despite different raw partition hashes:
A `5f0c997ddbc0a8380b4785d58048659f26efff5e7d173825972f3ca45646cc36`,
B `c4e3f3d25b3aefca70995c070faa177931a61738b4997acd52a6446daee4cf01`.
The captured `rootfs_data` mappings differ (9 versus 64 populated LEBs); the stock system archive
excludes that writable tree. Candidate overlay contents therefore need an explicit fresh/preserved
policy, rather than silently importing unknown overrides. The case-preserving stock archive also
excludes `/dev` and xattrs; it is an analysis input, not a complete ready-to-flash filesystem recipe.

## Signature/content gate remains distinct from recovery

In either verified `rootfs_sig` image, `[0xcc9,0xce9)` is digest
`00216f21e84f908f5f862de55af51375fdf032dbf413e98b160d9ab2d65a9c44`, and big-endian
`[0xd0c,0xd10)` is length 31,274,410. Both match the stock reconstructed SquashFS.
The generic new SquashFS instead has `bytes_used` 3,725,407 and digest
`e98c052ab8dba77d68a0a6535521f72daa8d9913c996317cb55428fa69e6dd75` over exactly that length.
Thus existing stock signed metadata does **not** describe this different payload. No matching vendor
signing capability has been established.

[LK evidence](../BOOT-FLOW.md#lk-failure-path-offline-analysis-2026-10-28-40) proves that a returned
certificate-verifier error panics/spins. It does not prove that this content mismatch is detected by
LK or after handoff. Earlier bounded kernel/userspace searches did not establish a consumer; they
cannot be turned into a guarantee of acceptance. SBC off, valid stock certificates and the recovery
PASS are insufficient to declare a custom rootfs bootable. Keep certificate-failure and valid-certificate/
different-content experiments separate; this audit constructs or authorizes neither boot experiment.

## First-A boot must preserve stock B

The archived `etc/rc.d/S99zmtk_boot_done` enables `etc/init.d/zmtk_boot_done`. Its A/not-successful
NAND branch calls `ab_image_sync "_b"` at line 42, before success writes at lines 49–55.
`lib/upgrade/bootctrl.sh:275–292` iterates the destination slot's entire list; `:325–346`, especially
`:335`, streams the opposite slot into those NAND partitions. The B list (`:39`) includes LK, TEE,
boot, signature, rootfs and modem/tinysys peers. The completion script also has a preloader-backup
copy branch (`:30–38`) and retry-triggered other-slot repair (`:118–141`). Disabling just rootfs
cloning would not preserve B.

The first candidate must prevent this **whole completion/synchronization path** from running in its
effective filesystem, including writable overrides, while providing separately reviewed success handling.
Stock `platform_do_upgrade` (`lib/upgrade/platform.sh:191–198`) is not a narrow deployment helper:
it dispatches broader A/B upgrade handling and clears shared `boot_para`.
The metadata helpers also write four copies in `misc` (`bootctrl.sh:68–77,92–103`). Their intended
priority changes are source evidence, not a demonstrated safe slot API. `get_current_slot` compares
priorities (`:263–272`); actual UART `bootslot` and root mount must establish the selected slot.
LK contains `set active slot: not supported!`; that diagnostic is not a verified switching API. Manual A selection,
reversal and reset-time retry policy remain unverified; stock B cannot be promised as automatic fallback.

## Next implementation and present verdict

Proceed with **local assembly preparation**, keeping the full stock boot/kernel and using the modern
tarball, this unit's selected vendor closure and 4.19 module/autoload/package records. Require a
case-sensitive build filesystem, explicit initial LAN/key-only access, fresh overlay policy and no
stock cross-slot clone path. Produce a new bounded UBI candidate and inspect its actual filesystem,
volume table, capacity, hashes and init paths before considering device use. The Docker CLI exists,
but its daemon was not running during this audit; no new container/image/tool was installed.

Before any first-A flash/boot, review exact slot-selection/reversal metadata writes and a deployment
operation limited to the final candidate's range/hash with stock-B/shared-state guards. Existing
recovery entry commands deliberately accept only `rootfs_sig_a` originals/the test pattern and cannot
deploy an arbitrary `rootfs_a` candidate. A new image-specific operation needs review and approval;
there is no request here to repeat the completed recovery drill.

Private machine-readable evidence: `private/build/native-input-audit-sli42581/artifact-audit.json`.
The prior extraction manifests, original partition hashes, archive member content and current build
manifest are the sources. No proprietary binary, raw image, private identity data or SDK content is
published. **Verdict: GO for offline assembly; no ready custom image and no custom-flash approval.**
