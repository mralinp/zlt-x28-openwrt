# LK boot/recovery authentication: local Ghidra preview (#211)

**Status, 2026-11-01: implemented in a local Ghidra database only.** No firmware was exported,
flashed or executed. The source LK dump remains unchanged. This follows the [authentication map](lk-authentication-ghidra.md)
and the readable function/variable annotations in #209 / PR #210.

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
