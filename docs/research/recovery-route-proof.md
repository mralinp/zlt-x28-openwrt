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

## Check 1, attempt 3 (2026-10-29): AB module still not found

Extra scans over `pl.bin` for any code that reaches the AB strings (`[QL_AB]`, `[AB] ...`, `no valid slot`,
`rollback_slot`, `ab init fail`, `get part misc fail`):

- Thumb `ldr`/`ldr.w` + `add rX,pc` and ARM `ldr` + `add rd,pc,rm` (PC-relative offsets): 312 string references
  resolved, none to those strings.
- Absolute pointers: only the four-entry table at file offsets `0x3d4c4-0x3d6ec` (base `0x208488`) points at them.
  Thumb `movw/movt` pairs (no consecutive pair exists) and ARM `movw/movt` (one value, unrelated).
- The main function reaches globals through a GOT whose base is `0x246564` (file `0x3e0dc`): `ldr rX,[pc]` literal +
  `add pc`, then `[base + literal]`. No GOT-relative literal lands on the descriptor table's records.

So the AB module is reached through something these scans do not model (an indirect call table, a stage copied to a
different base, or code in a region not in this payload). Further hand scanning has low yield; a full Ghidra
auto-analysis with the GOT/relocations applied, or a live observation (check 3), are the remaining routes.

## Decision rule for gate 6

- `rootfs_a` sessions: the preloader window precedes nothing they change (`misc` still selects B), so gate 6 is
  satisfied by the existing passes (#58-#72) plus step 2.
- `misc` sessions (identical, write, restore): need step 1 to pass, or step 3 to have passed with the
  `BROM-ROUTE-PROVEN` attestation naming which check proved it.

## Not covered

Power loss during the preloader's own flash accesses; SD/eMMC-style failure modes that do not apply to this NAND;
and an erased or corrupt preloader (BROM), which these sessions cannot cause.
