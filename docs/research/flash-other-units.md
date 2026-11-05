# Flashing a unit other than the first one, with no UART and no SSH (#318)

The guarded flash tools (`slot_entry.py`, `slot_session.py`, `restore_entry.py`) are pinned to the first unit. A second unit
(X28 PRO, board `TZ7.823.805A`, stock 8.6.8 built 2024-02-20, no SSH, no UART wanted) was backed up over USB on 2026-11-05.
Comparing its 51 images with the first unit's backup:

- **Identical (32):** `boot_a/b`, `lk_a/b`, `tee_a/b`, `rootfs_sig_a/b`, the modem and firmware images (`md1img`, `md1dsp`, `spmfw`,
  `sspm`, `mcupm`, `dpm`, `medmcu`, `pi_img`), `mcf1/2`, `proinfo`, `para`, `raw1/2`. The kernel image and boot chain are the same.
- **Different (19):** `rootfs_a/b` (other stock build), `preloader` and `preloader_backup`, `misc`, `boot_para`, `seccfg`, `protect1/2`,
  `nvram`, `nvcfg`, `nvdata`, `expdb`, `loader_ext_a/b`, `qraw`, `user_config`, `productinfo`, `user_data` (per-unit data and settings).
- The second unit's `misc` records are `0e0001010f000101`; the first unit's stock was `0e0001000f000100`. Read as Android-style slot
  metadata (priority, tries left, successful, verity-corrupted per slot), only the verity flag differs.

## Which pins are about the family and which about the unit
| Pin in `slot_session.py` | Second unit | Treatment |
|---|---|---|
| `ROOTFS_SIG`, `BOOT_SHA`, `LK_A`, `TEE_A` | identical | stay pinned: they define the supported boot chain; a unit without them is refused |
| `ROOTFS_A_SHA`, `ROOTFS_B_SHA`, `ROOTFS_B_HEAD_SHA` | differ | come from the user's verified backup |
| `MISC_SHA`, `MISC_A_SHA`, `BOOT_PARA` | differ | `MISC_SHA`, `BOOT_PARA` from the backup; the A-selected `misc` is computed from the user's own record |
| `MISC_BEFORE` / `MISC_AFTER` | flags differ | validate the record shape (magic, B-selected priorities) and change only the priorities and A's tries and success bytes, keeping each slot's verity flag |

## No UART, no SSH
- `check_uart`: with `--no-uart` the gate is waived on an explicit opt-in whose typed phrase says so; everything else still holds.
- `active_slot` over `ssh router`: replaced by a USB check. The DA reads `misc` now and it must equal the backup's `misc`, and the
  backup's `misc` must show the expected slot. The tools then know the slot state is what the backup recorded.
- Stronger read-back: after the write, `rootfs_a` is read back and compared in full, every neighbor partition is re-read, and `misc`
  is compared again.
- Way back without UART: restore from this unit's own backup over USB (`restore` mode) must be rehearsed before the write.

## Order
1. Pins from the backup (family pins stay), with tests on both units' real `misc` records.
2. USB live-slot check replacing SSH when SSH is unavailable.
3. `--no-uart` opt-in.
4. Rehearsal on the second unit, then the write. The router-safety-auditor reviews each step before it merges.

Not done: nothing here is implemented or proven on hardware.
