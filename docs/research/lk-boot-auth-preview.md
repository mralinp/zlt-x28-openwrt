# LK boot/recovery authentication: local Ghidra preview (#211)

**Status, 2026-11-01: implemented in a local Ghidra database only.** No firmware was exported,
flashed or executed. The source LK dump remains unchanged. This follows the [authentication map](lk-authentication-ghidra.md)
and the readable function/variable annotations in #209 / PR #210.

## How the original check works

LK authenticates the selected **boot image before starting Linux**. The loader at file `0xee12`
chooses `boot` or `recovery`, adds the slot suffix and asks the partition policy whether authentication
is required. The policy call at `0xee58` saves its result in register `r9`: zero skips these checks;
nonzero enables them. Simplified analyst pseudocode, not recovered or rebuildable vendor source:

```c
required = partition_authentication_required(selected_partition);
read_boot_header();
if (required) {
    assert_success(verify_image_certificate_chain());
    assert_success(verify_image_header_sha256());
}
read_image_components();
if (required)
    assert_success(authenticate_image_payload());
parse_image_and_prepare_kernel();
```

| Check / call offset | Purpose established from the original code |
|---|---|
| Certificate chain / `0xeef0` | Processes image/certificate metadata and invokes certificate verification helpers, populating authentication state. Deeper trust-anchor validation remains partly unaudited. |
| Header / `0xeefc` | Checks header length and compares its calculated SHA-256 with the saved certificate-derived digest at VA `0x8405e534`. |
| Payload / `0xef7c` | Compares a calculated 32-byte authentication result with saved expected state at VA `0x8405e510`. The calculation invokes the secure monitor; its full semantics remain unknown. |

A hash detects changed bytes; certificate verification authenticates the metadata supplying the expected
values. Replacing an image and calculating a new untrusted hash alone would not establish acceptance.
These are distinct checks, not a single comparison of a magic value.

An enabled check returning an error reaches an assertion call at `0xf004`, `0xf026` or `0xf048`.
The traced panic route disables interrupts at `0x8c7c` and spins at `0x8c7e`; it does not immediately
try the other slot. A later watchdog reset and reset-time slot policy are separate questions.
The detailed [authentication map](lk-authentication-ghidra.md#2-boot-image-path) records the callees and policy table.

The preview changes **BEQ (branch if equal) to B (branch unconditionally)** at the two skip gates below.
It does not insert NOPs or make failed cryptographic calls return success: those calls become unreachable
through this loader. Image reading, parsing and other error checks remain. The separate rootfs-certificate
check is still present. Also, `sbc_en = 0` is not sufficient to infer this policy is disabled: the original
software configuration at file `0x3e380` is `0x11`, which can select authentication independently of that log value.

## Open the saved graphical project

Local project: `private/research/lk-boot-auth-preview/project/X28_LK_Boot_Review.gpr`.
The `.gpr` and sibling `.rep` directory belong together; both are private and ignored by Git.

Double-click either program in Ghidra's project window:

- `LK_ORIGINAL.bin`: unchanged original bytes, named functions and variables.
- `LK_BOOT_RECOVERY_PREVIEW.bin`: the same analysis with the two instruction changes below.
  **The imported `.bin` on disk still contains original bytes. Only this program's saved database
  memory is patched.** Its imported source hash therefore identifies the original; use the mapped
  hash in Program Properties → X28 Review or the verification log for the preview identity.

Open Window → Bookmarks and choose **00 START HERE**. In Symbol Tree → Namespaces → Boot,
start with `load_boot_or_recovery_image` or `prepare_kernel_from_selected_image`.
Press G and enter `8400ecdc` or `8400ed72` to inspect the two branches. The decompiler shows
the authentication blocks in the original; the preview makes the existing skip branches unconditional.
Rootfs, Policy, Crypto and Failure namespaces retain their separate paths and explanatory comments.
Function/variable names describe analyst-inferred roles, not recovered source symbols.

## Exact change and scope

Input is this unit's 2 MiB `mtd25-lk_a.bin`, identical to `mtd38-lk_b.bin`:
SHA-256 `0ad94f065ebcfeefd157640d179b1b52779829a85179d07d38dd818b79007156`.
First-payload VA = file offset + `0x83fffe00`.

| File instruction / VA | Original | Preview | Unchanged destination |
|---|---|---|---|
| `0xeedc` / `0x8400ecdc` | `17 d0` — conditional `beq` | `17 e0` — unconditional `b` | File `0xef0e`, VA `0x8400ed0e` |
| `0xef72` / `0x8400ed72` | `07 d0` — conditional `beq` | `07 e0` — unconditional `b` | File `0xef84`, VA `0x8400ed84` |

**CONFIRMED static effect:** the first branch skips certificate-chain and header authentication
calls at `0xeef0` / `0xeefc`; the second skips payload authentication at `0xef7c`.
Only bytes `0xeedd` and `0xef73` differ (`d0 → e0`). The loader's policy call at `0xee58` remains
unchanged, along with the certificate/header/payload verification helpers themselves.
This preserves the policy query's existing initialization behavior; it does not classify that behavior
as read-only when LK actually runs. Nothing here executes LK.

The candidate affects **boot and recovery** loading. Caller file `0x4448` calls the loader at `0x4466`
with argument 1 for mode 2/recovery, or at `0x4496` with argument 0 otherwise/boot. It later reaches
kernel preparation at file `0x3e3a` through call `0x45cc`. The header parser at file `0x33c8`
(VA `0x840031c8`, called at `0xef86`) checks `ANDROID!` and caches header fields.
Those observations do not establish the absence of further checks throughout the boot chain.

The rootfs-certificate wrapper at `0x248c2` and its fatal failure path are untouched. Generic image
loading, `boot_para`, modem verification, seccfg, boot images and slot selection are not patched.
No hardware fuse, lock state or secure-boot configuration was changed.

The partition contains another MTK header at file `0x3fe00`: magic `0x58881688`, name `aee_lk`,
payload length `0x3ede4`, payload start `0x40000`. The first header names `lk`, length `0x3ed7c`,
payload start `0x200`. The complete second image is unchanged; its selection/execution path and
load address are **UNKNOWN**. Duplicate strings do not justify patching it at guessed offsets.

## Reproduce and verify locally

Use an installed Ghidra/JDK. In a **new private project**, import a byte-identical copy of the original
under each descriptive name above. Run `LkAuthentication.java` on both before the preview script;
the names/variables shown here use its #209 version (commit `f4ed667`). The initial #207 script also
provides the required analysis, but without all of those presentation annotations.

For each import, use raw `ARM:LE:32:v8`, compiler `default`, base `0x83fffe00`, `-noanalysis`, then:

```sh
# Original program:
-postScript LkAuthentication.java -postScript LkBootAuthPreview.java original

# Separate preview program, initially imported from ORIGINAL bytes:
-postScript LkAuthentication.java -postScript LkBootAuthPreview.java apply

# After saving, close the GUI project before reopening it headlessly:
-process LK_BOOT_RECOVERY_PREVIEW.bin -readOnly -noanalysis \
  -postScript LkBootAuthPreview.java verify
```

These are argument fragments for `support/analyzeHeadless`; project/import arguments follow the
[existing reproduction](lk-authentication-ghidra.md#reproduce-locally). Keep both script directories
in `-scriptPath` if using a private copy of the #209 annotations. Never run `apply` on the original
program you want to preserve. The script has no binary export or device operation.

The script refuses unknown source hashes, wrong language/base, changed mapped bytes and repeated
application. It verifies the entire mapped 2 MiB against the expected two-byte delta, both decoded
branch lengths/targets, and unchanged source bytes. `verify` makes no metadata or byte changes.
Require the explicit `BOOT AUTH ... VERIFIED` marker; Ghidra can exit zero after a script error.

## What is needed to patch, build and replace it

**The following steps are a proposed workflow, not completed deployment work or flash commands.**
Saving the Ghidra preview has completed only the local analysis stage.

### Binary patch versus rebuilding

For the selected two-branch change, **LK does not need recompilation**: produce a new copy of this unit's
original machine code with exactly the two byte changes. Ghidra's decompiled C cannot be compiled back
into the original LK. A genuine source rebuild is a different task requiring matching X28 LK sources,
board configuration, compiler/linker settings, memory layout and the image/container signing pipeline.
This analyzed LK body is ARM32/Thumb-2 even though the Linux kernel is ARM64.

The supplied FG360 SDK does not currently establish such a rebuild. Its
`sdk-fg360/release_sdk/openwrt/package/mtk/boot/lk/Makefile:3` selects a prebuilt directory;
lines 17–19 select `lk_raw.img` / `lk.img`; `Build/Compile/lk` at lines 32–34 only creates a directory;
lines 36–39 copy the existing images/configuration. Those package steps do not compile LK source.
The sibling-device prebuilts are not validated X28 replacements and must not be flashed.

### Remaining stages, in order

1. **Resolve the preloader/container boundary offline.** Trace how the preloader loads/authenticates
   the first LK image and when `aee_lk` is selected. Determine which headers, lengths, checksums and
   signatures cover modified bytes. Our bypass operates after LK starts; it cannot make the preloader
   accept a rejected LK. Neither `sbc_en = 0` nor the current OpenWrt boot settles this boundary.
2. **Produce a private binary candidate with a manifest.** Implement a small hash-bound patch/export
   step that requires the original 2 MiB size and SHA above, verifies `17 d0` / `07 d0`, writes a new
   file without overwriting its input and rejects unknown or already-patched input. Preserve both MTK
   headers, the complete `aee_lk` image and all other bytes. Before any additional container changes,
   the exact two-byte candidate must hash to
   `43afcc18be84e950534d78ed1ca6706cde4aa97a09911425a8e8576a63f71a92`.
   Reimport that actual output independently and verify its complete byte delta and branch targets.
   Do not export a relocated memory fragment, ELF or headerless payload as a partition replacement.
   If step 1 requires further changes, stop and review a new manifest/hash; this preview is insufficient.
3. **Prepare an LK-specific write and restoration procedure.** Bind it to this unit, the exact candidate,
   original backup, target geometry and neighbor/other-slot guards. Require dry-run evidence, full target
   read-back, fresh UART capture and a reviewed route to restore original LK if Linux cannot start.
   Existing recovery success covered rootfs/rootfs-signature targets, not recovery from broken LK.
   Keep the original full backup and verified second copy. This stage needs its own issue/review before use.
4. **Choose an inactive experimental slot without sacrificing the known-good chain.** The last read-only
   observation was slot A active. Do not overwrite active `lk_a`, or choose `lk_b` merely because B is
   inactive: B is the stock recovery chain. If A is the target, first review a transition to known-good B
   and the boot-counter/stock-sync behavior; no transition is performed here. Stock B can erase/repair A
   when A's tries exceed three, and its boot-completion scripts can synchronize slot images. USB writes
   to `misc` remain unproven; do not improvise a slot switch. See [boot flow](../BOOT-FLOW.md) and
   [measured counter/recovery limits](../TESTING.md).
5. **Test modified LK with the unchanged stock boot image first.** After exact owner approval of the
   artifact, target, restore plan and device operations, write only the chosen inactive LK partition through
   the reviewed guarded procedure. Verify the whole target and guards before a separately approved boot;
   stop on an unverified result. Keep `boot_*`, `rootfs_sig_*`, preloader and security configuration unchanged
   during this LK-only test. A successful boot would establish acceptance of that modified LK with that
   stock image; it would not prove an unsigned kernel works or that the bypass was necessary.
6. **Build and test the custom kernel as a separate change.** This is the real cross-compilation step:
   validate matching MT6890/X28 kernel sources, board DTB, configuration, drivers and ARM64 toolchain,
   including module ABI/versioning requirements. Reconstruct the observed Android boot container with
   correct component sizes, page alignment, addresses and DTB/ramdisk fields; do not flash a raw `Image`
   or an unrelated SDK boot image. Review any authentication-trailer handling rather than guessing it.
   Then use a separately approved inactive-slot `boot_*` write/restore plan and UART test. No tested
   kernel build command or custom `boot_*` replacement workflow is established by this PR.

Current tools must not be repurposed by weakening their guards: `tools/recovery/write_verify.py`
accepts only an original verified backup for an identical rewrite, even for `lk_a`; it is not a modified-LK
flasher or a recovery path from an arbitrary changed target. `restore_entry.py` is limited to `rootfs_sig_a`,
and `slot_entry.py` to `rootfs_a` / `misc`. `slot_session.py` pins both LK hashes as original guards, so
modified LK also changes the assumptions of existing sessions. Review that interaction before deployment;
do not edit tools during a hash-bound receipt chain or alter a backup manifest to make a candidate pass.

## Validation and limits

Validation logs and the saved databases stay in `private/research/lk-boot-auth-preview/`.
The unchanged original was deliberately rejected when presented as a patched preview before the
patch was implemented. Positive application and an independent read-only reopen verified both
saved programs: 18 named functions and 100 named variables each, zero original-byte changes,
exactly the two preview-byte changes, and the three authentication calls visible in the original
decompilation but absent from the preview's reachable flow. The preview mapped-memory SHA-256 is
`43afcc18be84e950534d78ed1ca6706cde4aa97a09911425a8e8576a63f71a92`.
Repeated application, a wrong raw mapping and an unknown synthetic input were refused.
No router connection is part of this task.

**UNKNOWN / not tested:** preloader acceptance of modified LK, any LK container signature/integrity
requirements, later verification or secure-monitor behavior outside the mapped gates, alternate
payload execution, custom-kernel compatibility and a successful hardware boot. The preview is an
inspectable local experiment, **not a flash-ready or hardware-approved image**. Device work needs
a separately reviewed artifact and restoration procedure plus exact owner approval.
