# Recovery: backup and USB flash access

How to back up the X28's NAND and reach it over USB when Linux no longer boots.
Tracks issue #4 (way back to stock); builds on #1 (partition dump).

> **Status, 2026-10-22:** full backup taken and verified. USB recovery port, chip security
> state and download-agent loading are confirmed. **Reading flash over USB is not working
> yet**, and no write or restore has been attempted. Do not flash experimental firmware
> until a USB read matches the backup and a restore has been tested.

| Step | Script | Result |
|---|---|---|
| 1. Back up every partition over SSH | `dump_partitions.py` | ✅ 51 partitions, 1,072,168,960 bytes (2026-10-20) |
| 2. Verify and unpack the backup | `verify_backup.py` | ✅ all sizes and SHA-256 match |
| 3. Find the USB recovery port | `usb_watch.py` | ✅ preloader `0e8d:2000`, needs a USB-A-to-C cable |
| 4. Install the USB tool | `setup_mtkclient.py` | ✅ mtkclient v2.1.4.1 plus 3 local fixes |
| 5. Read boot security | `target_config.py` | ✅ secure boot, SLA, DAA all **off** |
| 6. Read a partition over USB, compare hash | `read_verify.py` | ❌ download agent loads, but rejects `READ-FLASH` as unsupported |
| 7. Restore a partition over USB | none | not started |

## Safety rules

- **Read-only by default.** Every script here only reads from the device. The download agent
  runs in the modem's RAM, which is cleared at power-off.
- After any `mtkclient` command the modem stays in the preloader or download agent and
  **does not boot** (no internet) until its power is cycled. That is expected.
- Never upload the raw partition images through LuCI, concatenate them, or write them blindly.
- Backups contain the unit's identity, calibration and credentials. They live in `private/`
  (git-ignored). Never publish them or use them on another unit. Keep a second copy offline.
- Write or erase work (`risk/brick`) needs a USB read that matches the backup, a tested
  rollback, UART access (#2) and only the inactive A/B slot.

## Hardware setup

| Item | Detail |
|---|---|
| Cable | **USB-A to USB-C**, into a USB-A port (a hub or adapter is fine) |
| Does not work | USB-C to USB-C: the Mac never sees an attach, so the preloader finds no cable and skips USB |
| Host | macOS on Apple Silicon. `usb_watch.py` is macOS-only; the other scripts are portable |
| Router access | `ssh router` (port 2222, key auth) for step 1 |

Why C-to-C fails (inferred, not measured): the Mac logged no USB-C attach and no accessory
event in two power cycles, which fits a modem-side port without CC pull-down resistors.
The preloader confirms it checks for a cable first (`PMIC not dectect usb cable!`).

## Prerequisites

```bash
brew install libusb
```

```bash
/opt/homebrew/bin/python3.14 tools/recovery/setup_mtkclient.py
```

Steps 1–3 need only the Python standard library.

## Procedure

Run every command from the repository root.

### 1. Back up all partitions (SSH)

```bash
python3 tools/recovery/dump_partitions.py
```

Writes `private/backups/<date>/` with one gzip per partition, `manifest.json` (size,
SHA-256, ECC notices) and `/proc/mtd`. Uses `nanddump --bb=padbad -q`: main data with ECC
correction, bad blocks padded with `0xFF`, **no OOB**. About 1 GiB of reads; the router
keeps working, but expect extra heat.

### 2. Verify the backup

```bash
python3 tools/recovery/verify_backup.py private/backups/YYYYMMDD
```

Unpacks `images/mtdNN-<name>.bin` and writes `SHA256SUMS`. Any size or hash mismatch stops it.

### 3. Watch for the recovery port

```bash
python3 tools/recovery/usb_watch.py
```

Then cycle the modem's power. Expected:

```
+ 0e8d:2000 MT65xx Preloader <- MediaTek preloader/BROM: recovery port      (~1.1 s)
+ 2c7c:7003 RG500L-EU <- Quectel Linux USB gadget                          (~1.7 s, ~30 s later)
```

### 4. Install mtkclient

See Prerequisites. This installs `bkerler/mtkclient` at tag `v2.1.4.1`
(`5a863eece86fcaa97cb8325cf747e0aae3c307e4`) into `private/mtkclient/venv` and patches the
installed copy (the source checkout stays pristine):

| Fix | Why |
|---|---|
| uninstall `fusepy` | without libfuse it raises `OSError` at import; mtkclient only handles `ImportError`, so every command crashed |
| `check_sla()` returns "off" on an empty reply | this board's DA returns nothing for `DA.SLA`; mtkclient called `.decode()` on `False` (upstream `master` only guards `None`) |
| empty `page_parity_size` reads as `0` | this DA reports NAND with that field empty; mtkclient never uses it |

Running it again is a no-op.

### 5. Read the boot-security config

**Unplug the modem's power first** (mtkclient refuses a device that is already connected), then:

```bash
python3 tools/recovery/target_config.py
```

Plug the power in when it says it is waiting. Output is logged to `private/usb-probe/<date>/`;
the log contains the chip's ME_ID, which is why it stays private.

### 6. Read a partition over USB and compare

Same power order as step 5:

```bash
python3 tools/recovery/read_verify.py lk_b
```

`lk_b` is a good first target: 2 MiB, static, no identity data, and `lk_a` has the same
hash in the backup. The offset comes from the backup's `/proc/mtd`, the expected hash from
its `SHA256SUMS`. Add `--debug` to log the download agent's XML replies.

## Device facts

| | |
|---|---|
| SoC | MediaTek MT6890 (T750), mtkclient hw code `0x992`, subcode `0x8a00`, hw ver `0xca01`, sw ver `0x1` |
| Modem module | Quectel RG500L-EU (USB `2c7c:7003`) |
| Boot security (target config `0x0`) | SBC, SLA, DAA, root cert, memory read/write auth: **all off** |
| NAND | 4096-byte pages, 64-byte OOB, 256 KiB erase blocks; the 51 partitions span `0x3fe80000` (1 GiB minus 1.5 MiB) |
| Firmware | OpenWrt 19.07-derived "usr" build: `adbd` is not started; USB is unbound shortly after boot |
| Active slot at capture | `bootslot=b`, root `ubi.mtd=42` |

Partition offsets assume the `/proc/mtd` partitions sit back to back from 0. A matching USB read
(step 6) is what will prove this.

| Partition | mtd | Offset | Size |
|---|---|---|---|
| preloader | 0 | `0x00000000` | 4 MiB |
| preloader_backup | 1 | `0x00400000` | 2 MiB |
| lk_a | 25 | `0x11200000` | 2 MiB |
| boot_a / rootfs_a | 27 / 29 | `0x11500000` / `0x13600000` | 32 / 64 MiB |
| lk_b | 38 | `0x1d800000` | 2 MiB |
| boot_b / rootfs_b | 40 / 42 | `0x1db00000` / `0x1fc00000` | 32 / 64 MiB |
| user_data | 50 | `0x25300000` | 427.5 MiB |

### Bootloader observations (string scan of the backup, not decompiled)

- The preloader has MediaTek USB download, a key-triggered path (`download keys are pressed`)
  and an emergency download mode.
- It carries Quectel A/B boot control (`ab_bootcheck.c`: `tries_remaining`, `rollback_slot`,
  `no valid slot`). So a slot that keeps failing should roll back to the other slot. When
  exactly this triggers is not yet established.
- `misc` holds four copies of an `\0AB0` record. Its bytes look like slot A priority 14 and
  slot B priority 15, both marked successful; that field layout is a guess.
- The LK device tree names a `fusb304` USB-C controller, and the router lists `usb_type_c` on I2C
  with no driver bound. Whether the chip is fitted is unknown.

### Download agent (step 6) so far

mtkclient picks the `0x992` entry in `MTK_DA_V6.bin` (XML protocol, built 2021 for
`hw ver 0xca00`). Source paths embedded in it (`fm350-openwrt/.../mt6880/...`) show it was
built for the **Fibocom FM350 (MT6880)** module, not this board. Observed on 2026-10-22:

1. Stage 1 and stage 2 upload and run (≈1.1 MB/s).
2. `DA.SLA` property query: empty reply, about 2 minutes of USB timeouts, then treated as SLA off.
3. Hardware info: storage type **NAND**.
4. With every XML command logged next to the DA's first reply:

   | Command (as sent by mtkclient) | DA reply |
   |---|---|
   | `SET-…`, `HOST-…` (stage 1 setup) | `ERR!UNSUPPORTED` |
   | `NOTIFY-INIT-HW`, `SET-…`, `BOOT-TO` | `OK` |
   | `HOST-…`, `CAN-HIGHER-USB-SPEED`, `GET-SYS-PROPERTY` (`DA.SLA`) | `ERR!UNSUPPORTED` |
   | `GET-HW-INFO`, `EMMC-CONTROL` | `OK` |
   | **`READ-FLASH`** (`NAND-WHOLE`, `0x1d800000`, `0x200000`) | **`ERR!UNSUPPORTED`, "Unsupported command."** |

   mtkclient treats that XML-wrapped rejection as a non-empty (truthy) reply, which is why it
   printed an empty error rather than "Read flash isn't supported".

So this DA speaks a smaller, older XML command set and does not take `READ-FLASH`. Its strings
include `READ-PARTITION`, `READ-PARTITION-TABLE`, `NAND-WHOLE`, `NAND-AREA0` and `NAND-BMT`.

Next: read the DA's own partition table (`READ-PARTITION-TABLE`), then read `lk_b` by name
(`READ-PARTITION`). mtkclient's by-name path is broken for non-GPT storage, so this needs a small
direct call. Failing that, find the board vendor's own DA.

## Open questions

- A working USB read (step 6), then a write and restore tested on recoverable hardware.
- Entering BROM if the preloader itself is damaged (key combination or test point).
- How OOB/YAFFS2 metadata and bad blocks must be handled on restore (the backup has no OOB).
- UART access (#2) and the A/B rollback rules (#3).
