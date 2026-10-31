# Preloader slot logic (#152, transition step 2)

Offline, 2026-10-31. Thumb-2 disassembly of the verified `mtd00-preloader.bin` (SHA-256 `0f59889f...`), compared with UART
logs of real boots. Nothing was run on the router or written to it. Addresses are offsets into the image, which starts at
`0x40000` in the partition; the same image sits at `0x40000` in `preloader_backup`. The source path in the binary is
`platform/common/bootctrl/2.0/ab_bootcheck.c`.

**Verdict: the gate passes, and `misc` writes are safe to continue with. But failed boots do not reach recovery the way the
design assumed, so the design changes.** Rollback itself has still never been observed; only step 6 can show it.

## The record

16 bytes after the magic `00 41 42 30` and four `ff`: A at `+8` and B at `+12`, each priority, tries, success, up-type.

| Byte | Used for | Evidence |
|---|---|---|
| Priority | A boots if A's priority is equal or higher, otherwise B (`0xabc`). | Code; UART |
| Tries | Rollback when above 5 (`0x551c`). | Code; rollback not observed |
| Success | **Only printed.** It decides nothing (`0x54f2`, `0x5510`). | Code |
| Up-type | FOTA steps, see [the hazard below](#up-type-can-erase-the-preloader). | Code |

## What counts as a try

The counter does not count boots. It adds one to the slot with the higher priority only when the reset reason is a watchdog
reset carrying the bypass flag `0x2000`, or a PMIC full reset (`0x29104`, `0x22780`). That includes B: success plays no part.

| Boot | UART line | Tries |
|---|---|---|
| `reboot` | `WDT reboot bypass power key!` then `current solt:0,tries_remaining:N` | +1 |
| Power cycle | `Power key boot!` | unchanged |
| Brown-out | `pmic: power miss!` | unchanged |
| Watchdog without the flag | `WDT normal boot!` (code only) | unchanged |

The 2026-10-29 rehearsal log shows this: A stayed at 4 and then 5 through many `Power key boot!` lines and moved only on
`WDT reboot bypass`. The count is checked before it is added to, so a `reboot` at 5 reads 5 and leaves 6.

## Rollback

On a boot that reads tries above 5 (`0x54e0`):

1. **It is skipped if the boot looks abnormal** (`0x25978`): the RAM console holds a watchdog status other than 0, 2 or
   `0x800`, or an exception record. It prints `skip switch for abnormal in while boot failed` and stays on the slot. The next
   boot that is not abnormal goes ahead.
2. It sets the other slot's priority to `0f`, and lowers this slot to `0e` only if it was `0f` (`0xbb4`). Tries, success and
   up-type are kept. All four copies are written, and the boot carries on with no reset.
3. The other slot is not checked in any way. A failed write is not fatal: it prints the same `switch to` line and stays.

From A at `0f` this leaves B `0f`, A `0e`, so **the design's stop condition does not apply: A does not stay above B.** Stock
B then sees A's tries above 3 and repairs A, as expected. It is symmetrical, so B with tries above 5 switches to A. If both are
above 5 the slots alternate each boot, and neither is ever locked out.

## Damaged copies

Reads go through the copies from `0x800` up and take the first that reads without error and has the magic (`0x7d0`). There is
no checksum, and the other copies are not compared.

- **A skipped copy is repaired** from the good one, but only the copy just before it. A later preloader write fixes the rest.
- **All four bad:** the record is rebuilt as A `0f 00 01 00`, B `00 00 01 00`, and A boots. So `no valid slot!` is not reached
  from damaged copies. It needs both priorities at 0 (`0xcf4`), and the boot still continues, with boot mode 2.
- **A cut during a write is covered.** An erased copy has no magic, and an uncorrectable page returns an error
  (`0x526e`, inferred from there down). Either way the next copy is used.
- **The order in the design is right.** `0x800` is read first, so the old value holds until that last copy is rewritten, and a
  cut while rewriting it falls through to `0x40800`, which is already new.
- **Not covered:** a part-programmed page that still passes ECC and keeps the magic would be believed. Bit errors of that kind
  can only produce a wrong slot or count, which the mechanism above then handles, apart from up-type.

The preloader's own write erases each block and programs only the 32 bytes, copy 0 first. It does this on every counted
reboot, so the unit has lived with this exposure all along. It reads back into a null buffer and compares nothing.

## Up-type can erase the preloader

| Up-type | Action |
|---|---|
| 4 | Erases the erase block at `0x40000` in `preloader`, which is the primary image, sets up-type 1, resets (`0xdd8`, `0x552e`). |
| 1 | On rollback, erases that same block, switches slot, resets (`0x5592`). |
| 2 | Cleared to 0. |
| 0 | Nothing. |

This looks like the FOTA path for a new preloader, with the backup taking over; that part is inferred. **No tool may write
those bytes**, and a `misc` guard should refuse any record whose up-type is not 0. Both slots read 0 today.

## What this changes

- **A dead A does not reach rescue by power cycling**, however many times. It needs six counted reboots, and something has to
  issue them. See the design for the change that does.
- **Rescue must reset B's tries.** Otherwise six reboots of rescue switch to A.
- **An unexpected power cut does not add tries.** The "seven power cuts" accident in the design does not exist.
- **Kernel panics are still unknown.** Whether a panic reset carries `0x2000` or looks abnormal was not read; it depends on the
  kernel's reset path. If it looks abnormal, rollback waits for a boot that does not.
