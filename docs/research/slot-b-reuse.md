# What the preloader does without slot B, and what B is worth as storage (#302)

Read-only research, 2026-11-09. Sources: the verified 2026-10-20 dump, the saved Ghidra evidence of the X28 PRO unit's preloader
(`private/research/slot-access-20261106/`, re-disassembled here with Capstone), the UART logs of the flasher sessions
(`private/usb-probe/`), and the docs linked below. Nothing was run on or written to a router. Decision already taken, not reopened: the
way back is the download agent (DL) with [x28-flasher](https://github.com/mralinp/x28-flasher), not a recovery slot (#152, #153 closed).

**Marks:** *decoded* = read from the preloader's code, never run; *observed* = seen in a UART log; *inferred* = a reading with a gap.

## Answers in short

1. **The preloader looks only at the `misc` record, never at B's contents.** A is chosen unless B's priority is higher. A record that
   is wrong in all four copies is rewritten to "A first". The only thing that sends the unit to B is A's tries reaching **6** (*decoded*;
   never seen, the highest logged value is 5). B must then boot, or the unit loops or hangs until DL.
2. **DL can write every partition except `misc`, so it cannot change the A/B state or reset tries.** It does not need to as long as B
   stays a working stock slot. If B is repurposed, DL alone cannot bring back a unit whose `misc` points at B, and the flasher today
   cannot write B at all.
3. **Only `rootfs_b` (64 MiB) is plain data.** The other 134 MiB are signed boot chain, kernel and modem images.
4. **The gain is about 55–60 MiB (estimate) on top of 271 MiB free in `/overlay`**, and it costs the automatic stock fall-back.
   Recommendation: leave B as stock.

## 1. What the preloader and LK do with `misc`

### The record and how it is read (*decoded*, `ab_bootcheck.c` in the preloader)

`misc` offset `0x800` holds 0x20 bytes: magic `00414230`, four `ff`, then one 4-byte entry per slot at `+8` (A) and `+12` (B):
priority, tries, success, up-type. The routine at `0x201670` (addresses are VAs of the entry slice of the PRO unit's preloader)
reads copy 0 to 3 in order, `0x40000` apart, and **takes the first copy whose 4 magic bytes match**. There is no checksum. A write
(the same routine) erases and rewrites all four copies and reads each back.

| Step | Code | What it does |
|---|---|---|
| Choose slot | `0x20195c` | A unless `A.priority < B.priority`; **a tie goes to A**. |
| Magic wrong in all four copies | same | Prints `booctrl magic not match init default value` and writes a default: **`_a` is hard-coded**, A priority 15, success 1, B priority 0, success 1. A blank (`ff`) or zeroed `misc` therefore comes back as "boot A" (*decoded*, not observed). |
| `misc` unreadable | same | Prints `get_suffix read_partition_info failed` and returns no slot. |
| Both priorities 0 | `0x201b94` | Prints `[AB] no valid slot! boot_mode: %d`, sets a boot-mode global to 2 and returns without choosing. What mode 2 does is not traced (in MediaTek's usual list it is recovery; *inferred*). |
| Every boot | `0x2018ec` | Adds 1 to the chosen slot's tries byte (8-bit, no cap) and rewrites the record. This is the "try" in the docs. |
| Tries below 6 | `0x206380` | Prints `ab_suffix, ab_retry, ab_boot_success` and boots the chosen slot. Success is printed, **not used** in this routine. |
| Tries 6 or more | `0x206380` → `0x206330` → `0x201a54` | `ab_switch_boot_part`: the other slot gets priority 15, the one that held 15 drops to 14, tries are not touched, then the unit resets. A failed switch prints `[AB] Fail switch to %s`. |

**Corrections to older notes.** [slot-selection.md](slot-selection.md) inferred a limit of 3 tries. The limit in the preloader is 6;
the "above 3" is the *stock userspace* rule (`zmtk_boot_done` repairs A when it sees A's retry above 3). They combine: A with tries 6
is replaced by B, B then sees tries above 3 and clones itself over A. Observed in the logs: `ab_retry` 0, 1, 3, 4 and 5 all booted `_a`
(dozens of boots across the saved logs), `_b` with 0 and success 1 for the original stock state. Caveat: the code is from the **PRO unit's** preloader; the first
unit's build differs, but carries the same strings and source path. The same disassembly on its `mtd00-preloader.bin` is the
offline check still open.

### What this means when B is missing, invalid or repurposed

| B is | While A boots and tries stay below 6 | When A's tries reach 6 |
|---|---|---|
| Stock (today) | Not read. | B boots, stock repairs A (erases the native image), unit is back on stock B. This is the safety net. |
| Intact boot chain, `rootfs_b` replaced by data | Not read. | B's `lk_b`/`boot_b` start, the root mount fails, B's own tries count up, at 6 the preloader flips back to A. A loop between two broken slots. *Inferred*: never observed. |
| Erased or invalid (`lk_b`, `loader_ext_b`, ...) | Not read. | The preloader verifies `loader_ext_b`, `lk_b`, `tee_b`, `sspm_b`, `mcupm_b`, `pi_img_b` for the selected slot ([UART log](uart-boot-log.md)). What a failure does is **not known**: `sbc_en = 0` is printed and LK's rootfs check is fatal on error ([BOOT-FLOW](../BOOT-FLOW.md)). The unit may stop before the USB window. |

Nothing in the preloader checks that B *exists* while A is selected. The risk of repurposing B is entirely on the failure path.

### LK

LK does not choose or count. It takes the suffix and builds `bootslot=a|b` and `ubi.mtd=28|42` (`ql_raw_data_module.c`), answers
"set active slot" with `not supported!`, and its strings hold no retry, tries or priority names. It opens `misc` (`open misc fail`)
for the standard Android message at offset 0, which is empty. *Inferred*: LK never writes the A/B record; its code was not decoded
for this.

## 2. What DL mode can and cannot restore

- **Where the window sits.** In every boot log the order is: `misc` read and the tries increment, `loader_ext_<slot>` certificate
  check, `before bldr_handshake`, `[PLFM] USB cable in`, then the DA, or `sspm`/`lk` verification and LK. The window comes **before**
  `lk`, `tee`, `boot` and `rootfs` of either slot and after the choice of slot.
- **Observed:** every flasher session in `private/usb-probe/` ran with `misc` selecting **A** (`ab_suffix: _a`, tries 0 to 5) and the
  DA loaded; earlier sessions ran with B selected. So DL works with `misc` pointing at either slot.
- **Not observed:** DL with a blank, mixed or both-zero `misc`, with tries at 6 or more, or with a damaged `loader_ext_<slot>`.
- **Writes.** All partitions except `misc` (TESTING 28: the first block write was not acknowledged, twice; 42 on the PRO: the same and the agent stayed
  silent until a power cycle). The guarded `slot_entry.py` writes only `rootfs_a`; slot B is locked in the app. Its `CMD:ERASE-FLASH`
  was never tried on `misc`.
- **What DL therefore cannot restore:** the priority bytes, the tries and the success byte. After a DL write of A, a record with A's
  tries at 4 or 5 still counts: the next boot makes 6 unless the new image boots and `x28-bootok` resets them, and a record that
  was already flipped to B stays flipped.

**Can the flasher recover a unit whose `misc` points away from A?**

| Situation | Recoverable by the flasher today? |
|---|---|
| `misc` selects B, B is intact stock | **Yes**, the designed path: B boots, the app's *Boot order* step flips the priorities over SSH with `dd-nand`. After a fall-back this also needs the root-access step again, because stock repaired A and B's overlay is unchanged. |
| `misc` selects B, B repurposed or broken | **No.** DL could restore B's partitions from the backup, but no guarded tool writes B. A blank `misc` would heal to A (above), but nobody has shown DL can erase it. |
| `misc` selects A, A broken | **Yes**, DL rewrites `rootfs_a` (five images flashed). If the fall-back already fired, stock B repaired A and the unit is on B: previous row, intact case. |

## 3. What is in B's 198 MiB

Sizes from `/proc/mtd`; "used" is the end of the last non-`ff` byte in the 2026-10-20 dump. In that dump **13 of the 14 B partitions
are byte-identical to their A twin** (stock clones A from B in `ab_image_sync`); only `rootfs` differs.

| Partition (B) | MiB | Used (dump) | Kind | Can it move or be reused? |
|---|---|---|---|---|
| `rootfs_b` | 64 | 63.8 (UBI) | **Plain data**: stock squashfs (31 MB) + vendor overlay in UBI | **Yes**, the only candidate. |
| `rootfs_sig_b` | 1 | ~0 | Signature of the rootfs, read by B's LK only | Small; useless alone. |
| `boot_b` | 32 | 8.7 | Android boot image (kernel + dtb), signed | No: B's kernel. The empty 23 MiB tail is not addressable without a new layout (#181). |
| `md1img_b` | 80 | 32 | Modem firmware | No: A uses `md1img_a`, but the file is a fixed modem image, 48 MiB free in a raw partition only the loader reads. |
| `md1dsp_b` | 10 | 5.7 | Modem DSP firmware | No, as above. |
| `lk_b`, `tee_b` | 2 + 1 | 0.6, 0.15 | Bootloader, ATF, signed | **Must not move**: checked by the preloader, in the path after the USB window. |
| `loader_ext_b` | 1 | 0.04 | Preloader extension, signed | **Must not move**: verified **before** the USB window when B is selected. |
| `sspm_b`, `mcupm_b`, `pi_img_b`, `spmfw_b`, `dpm_b`, `medmcu_b` | 2+2+1+1+1+1 | < 0.4 each | Power, MCU and tinysys firmware, signed | **Must not move.** |

Not in the 198 MiB: `mcf1_b`/`mcf2_b` (8 MiB each, modem configuration), `loader_ext_b` (1 MiB, listed above) and the shared
partitions (`misc`, `para`, `expdb`, `nvram`, `nvdata`, `proinfo`, ...), which never belong to a slot. **Plain data: 64 of 198 MiB;
firmware that cannot move: 134 MiB.**

## 4. The real gain

| Source | Size | Cost |
|---|---|---|
| `/overlay` on `user_data` (UBI, extroot) | **271 MiB free** of 427.5 MiB | Already there, no new risk. |
| `rootfs_b` as a second UBI device (`ubiattach -m 42`, no layout change) | 64 MiB raw, **about 55–60 MiB usable** (estimate: 256 erase blocks of 256 KiB, two for the volume table, a bad-block reserve of about 1 % and UBI headers; not measured) | Gone: the stock fall-back and the clone-repair, and the loop risk in section 1. About +20 % over the overlay. |
| USB extroot | Any stick | A stick must stay in. The docs only show the `mtu3` controller (`usb@11201000`) and the USB-C recovery port; a **USB host port is not established** here. |

An extra 20 % is not worth losing the only automatic recovery. If B is wanted, the better use is a **second native slot**: 13 of its
14 partitions are already A's clones, so only `boot_b` (kernel) and `rootfs_b` would follow A. The preloader then gives a real A/B
rollback with no stock script, because the native image has no `zmtk_boot_done` and so no cross-slot repair. That is a design option for
#154, not a decision here.

## 5. What this means for sysupgrade (#154)

- **Where an interrupted or failed write to A lands.** `rootfs_a` is half-written but `rootfs_sig_a` and `boot_a` are not, and no
  content check of the rootfs was found ([BOOT-FLOW](../BOOT-FLOW.md)), so LK starts the kernel, which cannot mount the root. Each
  boot adds a try. Whether the kernel panics and resets by itself or hangs until the hardware watchdog fires is **not observed**; the
  command line has no `panic=`. If it resets, A tries reach 6 and the preloader flips to B; with stock B, B repairs A and the unit
  is back on stock, and the owner reflashes with the flasher. If it hangs before the watchdog, power cycles are needed to count.
- **DL is always the last resort:** the window opens on every boot before `lk` and the rootfs (observed with tries up to 5).
  Recovery needs a computer, USB-A to USB-C and the user's download agent.
- **Order of operations a sysupgrade should follow:** write and read back `rootfs_a` from RAM, and only then reset A's tries to 0
  (a fresh budget of 5 boots) and keep priorities as they are. It never touches `success`. A sysupgrade that rewrites `misc` early
  leaves a half-written A with a clean budget, which is the worst case.
- **If B is repurposed, sysupgrade has no backstop** except DL, and must say so.

## Smallest next tests (none run, each needs the owner's OK and a UART capture)

1. **Offline, free:** the same disassembly on the first unit's `mtd00-preloader.bin`, to confirm limit 6 and the default record there.
2. **First valid copy** (one byte, reversible): break the magic of copy 1 only with `dd-nand`, reboot, expect no `magic not match`
   line and a normal boot, restore. Confirms the read order that every `misc` write plan depends on.
3. **DL erase of `misc`:** erase copy 4 only through the agent while copies 1 to 3 are valid. If acknowledged, the next boot's tries
   increment rewrites all four copies, which also shows the rewrite. Decides whether a blank `misc` is a way back from DL.
4. **Tries at 6, with stock B** (a deliberate boot loop on the sacrificial unit with `x28-bootok` stopped): shows the switch, B's
   repair and the exact boots to fall back. This is the only way to settle section 5's open point and to see the `≥ 6` branch.

Related: [BOOT-FLOW](../BOOT-FLOW.md), [recovery-route-proof](recovery-route-proof.md), [misc-probe-plan](misc-probe-plan.md)
(its "which copy does the preloader read" question is answered above), [slot-selection](slot-selection.md), [RECOVERY](../RECOVERY.md).
