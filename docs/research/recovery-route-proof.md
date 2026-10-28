# Proving the way back before the first write (gate 6)

The auditor's top finding: every DA session so far ran on a booted stock-B unit, so "BROM/DA restore if neither
slot boots" is unproven. This note narrows what actually has to be proven, from evidence already on disk, and
orders the checks from free to risky. Nothing here writes to the router.

## What the recovery route is

Every restore so far entered through the **preloader's USB window**: power-cycle, `0e8d:2000` appears for ~1.1 s,
mtkclient loads the Quectel DA over it ([RECOVERY](../RECOVERY.md)). That needs a working preloader, not a working
slot, LK or kernel. True BROM (test point or key) only matters if the **preloader itself** is damaged. Neither planned
session writes the preloader (`rootfs_a` and `misc` only), so a damaged preloader is outside this plan; the
open question is narrower:

**Can a bad `misc` (blank or mixed slot records) stop the preloader before its USB window opens?**

## The finding that makes this a real question

From a recovery-entry capture (`changed-page-test-tq4nnbk9/uart.log`, line numbers within one boot):

| Line | Preloader step |
|---|---|
| 185 | `[PART]` table read |
| **239-240** | **`[QL_AB] metadata.slots[0].priority:14,...[1].priority:15`, `ab_suffix: _b`** |
| 279 | `[BLDR] Build Time` |
| **615-628** | **`before bldr_handshake`, `[PLFM] USB cable in`, `[TOOL] USB enum timeout/handshake`** (the USB window) |
| 634+ | DA jump (recovery) or `Loading LK` (normal) |

The slot decision is read and printed about 375 lines **before** the USB window. If the preloader treats an invalid
record as fatal (`no valid slot!`, `rollback_slot fail`, `invliad slot` are all in its strings), the window may never
open, and the DA route is gone exactly when `misc` is bad. If it falls back to a default or continues, recovery
still works. This is the single behavior the first `misc` write could change.

## Checks, cheapest first

1. **Offline, zero risk: read the preloader.** Disassemble `mtd00-preloader.bin` around the `no valid slot!` /
   `rollback_slot fail` / `invliad slot` strings and the `bldr_handshake` call. Question: on invalid or mixed
   records, does control reach `bldr_handshake`? Also decode the `download keys are pressed` path (which key), as
   a second entry that may skip slot logic. Pass: handshake reached on every invalid-record path, or a key path
   that is independent of `misc`. Fail or unclear: do not run any `misc` session.
2. **Passive, zero risk: one cold power-cycle capture** with `usb_watch.py` and the UART log together, to confirm
   the window (`0e8d:2000`) opens at the `USB cable in` line on this unit (it already did in #58-#72; this ties
   the two clocks together).
3. **Reversible probe, only if 1 is unclear:** with `rootfs_a` done and verified (B still selected), write a `misc`
   image where **one** of the four copies is changed to the A selection and three stay B. This is itself a `misc`
   write and needs the full gate set, but it tests the mixed-copy rule without ever selecting A by majority. It
   is not planned until 1 is unclear and the owner chooses it.
4. **True BROM** (test point or key combination, undocumented for the X28): only worthwhile if the preloader is
   ever written. Out of scope for these sessions; record as a stretch.

## Check 1, attempt 1 (2026-10-29): inconclusive

Tooling: `capstone` 5.0.7 (user site), plus ad-hoc scripts. `rea` could not help (no Ghidra configured; it refuses
raw images). What was established:

- `mtd00-preloader.bin` holds a GFH image at file offset `0x40000`: `file_len 0x3e96c`, load `0x200ea0`, jump
  offset `0x160`. Entry (`0x201000`) is a 4-word header, then **ARM** code (`b`, then `ldr r6,[pc,..]`, zeroed
  registers, `mrc p15`); the image relocates itself, and most literals are not near the load address.
- A link base of `0x208488` (4 of 10 error/status strings are pointed to by words there) puts the strings
  (`rollback_slot fail`, `[QL_AB] slot:`, `[QL_AB]current solt`, `check fail, slot`) in a pointer table at file
  offsets `0x3d4c4-0x3d6ec`, laid out as records (`{.., ptr, 0, ptr, .., 0x30001}`) rather than loaded by
  `ldr` literals. No ARM or Thumb `ldr`-literal reaches those words, so the log text is reached through a table
  or base register, and the control flow around `no valid slot` and `bldr_handshake` was **not** recovered.

The question stays open. A proper decompiler with this image loaded at `0x200ea0` (ARM entry, relocation visible)
is the way to continue; ad-hoc scripts are not enough for a table-driven, relocated binary.

## Decision rule for gate 6

- `rootfs_a` sessions: the preloader window precedes nothing they change (`misc` still selects B), so gate 6 is
  satisfied by the existing passes (#58-#72) plus step 2.
- `misc` sessions (identical, write, restore): need step 1 to pass, or step 3 to have passed with the
  `BROM-ROUTE-PROVEN` attestation naming which check proved it.

## Not covered

Power loss during the preloader's own flash accesses; SD/eMMC-style failure modes that do not apply to this NAND;
and an erased or corrupt preloader (BROM), which these sessions cannot cause.
