# Plan: learn how the preloader reads `misc` without ever selecting A (check 3)

**Plan only. It authorizes no write, power cycle or slot change.** Every step needs the gates in
[rootfs-a-write-plan](rootfs-a-write-plan.md) and its own explicit approval. Static analysis of the preloader
could not find the slot code ([recovery-route-proof](recovery-route-proof.md), attempts 1-3), so the preloader's
behavior has to be observed, or designed around.

## What a probe can and cannot buy

A probe write has the same hazard as the real one: the engine rewrites all of `misc` (four 256 KiB erase blocks) in
one DA request, and an interruption mid-write can leave a blank or partial block. The unknown that matters is
which copy the preloader trusts when copies disagree or one is blank. A probe that merely repeats the whole-partition
write teaches nothing about that and carries the same risk. So the plan has two parts: make the write itself much
safer, and *observe* the read policy with a write that never changes the selected slot.

## Part A: shrink the write hazard (blockwise, ordered)

1. **Rehearse block-granular writes on `rootfs_sig_a`** (inactive, already proven for whole-partition writes in
   #70/#72): an identical write of one 256 KiB block at `0x13500000 + k * 0x40000`. Pass: acknowledged, partition and
   all guards unchanged. This proves the DA accepts sub-partition block ranges; it has only been used for whole
   partitions so far. If it fails, Part A stops and the whole-partition risk stays.
2. **Engine mode `blockwise` for `misc`** (new issue): the same spec and pinned image, written as four separate
   requests, one erase block each, in a fixed order, with a readback of that block and all guards after each. At any
   interruption at most one block is blank or partial; the other three are intact.
3. **Order:** the copy the preloader trusts is written **last** (known after Part B; until then write 4, 3, 2, 1).
   An interruption then costs only the final block, never leaves all copies unusable, and a half-new record set
   still decodes to either B or the fully new A.

## Part B: read-policy experiment (selects B throughout)

One blockwise write sets the four copies to records that all still select **B** (B priority stays `0f`, A priority
`0e` today) but carry *distinct, visible* A priorities:

| Copy | Offset | A priority byte |
|---|---|---|
| 1 | `0x800` | `0x0d` (13) |
| 2 | `0x40800` | `0x0c` (12) |
| 3 | `0x80800` | `0x0b` (11) |
| 4 | `0xc0800` | `0x0a` (10) |

Everything else in the 16-byte record is the original. The preloader prints
`[QL_AB] metadata.slots[0].priority:N,metadata.slots[1].priority:15` on every boot, so one reboot reveals the
policy (A priority is `slots[0]`):

| UART shows `slots[0].priority` | Meaning |
|---|---|
| 13 / 12 / 11 / 10 | reads copy 1 / 2 / 3 / 4 (first, second, third or last-wins) |
| 14 | ignores all four (reads another place, e.g. `qraw`) |
| anything else, or `no valid slot`, hang, no boot | copies disagreeing is fatal or confusing: restore at once |

Then restore the original `misc` with the same blockwise mode and confirm 14 on the next boot. No step selects A,
so `rootfs_a` is never booted and the probe does not depend on the custom image. Two blockwise writes, two reboots.

## Stop rules

- Any acknowledgement failure, hash mismatch or guard drift: stop, no retry, no reboot; restore the block that was
  being written with the engine's restore mode.
- After the probe reboot: anything but one of the `13/12/11/10` lines within the normal boot time: do not repeat; use
  the USB window (`usb_watch.py`) and restore. If the window does not appear, the route is not proven and
  the unit needs BROM (undocumented for the X28): stop there, do not experiment further.
- The restore write needs its own approval before power-cycling for the second reboot.

## What each outcome unlocks

- Policy is a single deterministic copy `k`: write `k` last in the real A-selection; interruption risk is one block.
- Policy is "first valid / majority": same, with copies written so a valid majority exists at every moment.
- Anything unexpected: the real `misc` session stays blocked; the BROM route becomes mandatory work.

## Gates before Part A step 1

The write-plan gates 1-8 apply (tools merged with host tests; auditor sign-off; backup copy; UART up; entry command
used with typed approval; recovery route proven or explicitly accepted as unproven by the owner; `zmtk_boot_done`
re-read; approval of the exact target). Part A step 1 touches only `rootfs_sig_a`, the proven inactive target, and is
the first hardware step to run.

## Not covered

Partial programming inside a block (page-level tears), the unlikely case that the preloader checks a CRC we have not
seen, and `qraw` as an alternate selector (the experiment would show it as "14").
