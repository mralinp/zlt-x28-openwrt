# x28flash: a single-binary Rust USB tool (#240), dropped

> **Dropped (#270).** The Rust tool was removed; flashing stays on the maintained, patched mtkclient in `tools/recovery/`.
> This note is kept only for the protocol and DA findings below.

Design for replacing the Python + patched mtkclient chain in `tools/recovery/` with one downloadable binary.
Phase 1 (this document plus `tools/x28flash/`) is **read-only**: detect the modem, load the download agent (DA),
read partitions and verify them by SHA-256. There is no write code path. Writes are a later phase that needs this
design reviewed by the router-safety-auditor and the owner's approval first.

**Status, 2026-11-02:** host-tested only; reviewed by the router-safety-auditor (OK with changes, applied). The tool has **not** touched the unit. Every USB claim below about the
X28 comes from the mtkclient sessions recorded in [RECOVERY.md](../RECOVERY.md) and [TESTING.md](../TESTING.md),
not from x28flash.

## Why

Today a USB read needs git, Homebrew libusb, Python 3.10+, a venv, a pinned mtkclient commit and four source
patches (`setup_mtkclient.py`). That works for the owner's Mac and nobody else. The goal is one file per platform
that runs with no install step, guides the user (prompts, spinners, progress bars, coloured errors) and refuses
anything outside what was proven on this board.

## USB without a system libusb

| Option | Verdict |
|---|---|
| **`nusb` 0.2** (pure Rust: IOKit on macOS, usbfs on Linux, WinUSB on Windows) | **Chosen.** No C code, no system library: the macOS release binary links only IOKit, CoreFoundation and libSystem; Linux builds as a static musl binary. |
| `rusb` with `vendored` libusb | Works, but compiles C libusb per target, and on Windows it still needs WinUSB bound to the device, so it buys nothing over nusb. |
| Serial port (the preloader is a CDC-ACM device) | mtkclient has a serial handshake. Useful later on Windows, where `usbser.sys` binds the port by default and nusb cannot open it without a driver change. Not in phase 1. |

What the X28 preloader exposes (descriptors logged on 2026-10-22): `0e8d:2000`, interface 0 CDC control
(interrupt `0x83`), interface 1 CDC data, bulk OUT `0x01` and IN `0x81`, 512-byte packets. x28flash claims both
interfaces, sends mtkclient's line coding (921600 8N1) and RTS on interface 0, and talks on the bulk pair.

Platform notes, none verified with x28flash yet:

- **macOS:** claiming goes through IOKit. libusb (mtkclient) uses the same call on this Mac and it worked, so nusb
  is expected to work; if macOS's CDC driver holds the interface, the claim fails with a clear error.
- **Linux:** `cdc_acm` binds the port; nusb detaches it when claiming. Non-root users need a udev rule
  (`SUBSYSTEM=="usb", ATTR{idVendor}=="0e8d", ATTR{idProduct}=="2000", MODE="0660", GROUP="plugdev"`).
- **Windows:** bind WinUSB to `0e8d:2000` (e.g. Zadig), exactly as mtkclient requires. A COM-port backend would
  remove that step.

Reads use sized bulk transfers: x28flash asks for exactly the missing bytes (rounded up to whole packets), as
mtkclient's sized `usbread` does. A larger request could wait for a short packet the DA never sends while it waits
for our ACK.

## The protocol as mtkclient `7cb40e7` uses it on this board

Sources: `mtk_preloader.py`, `Port.py`, `Library/DA/xmlflash/xml_lib.py`, `xml_cmd.py`, `daconfig.py` at the pinned
commit, and the unit's mtkclient logs (`private/usb-probe/20261022/`, not committed).

### Preloader (`brom.rs`)

| Step | Host sends | Device answers |
|---|---|---|
| Handshake | `a0` alone (preloader PIDs only), then `a0 0a 50 05` one byte at a time | each byte's complement `5f f5 af fa`; 5 tries, draining the IN side between them |
| `GET_HW_CODE` | `fd` (echoed) | u32 BE: hw code `0x992` in the top half, hw ver below |
| `GET_TARGET_CONFIG` | `d8` (echoed) | u32 BE config (`0x0` on the X28: SBC, SLA, DAA all off), u16 BE status |
| `GET_BL_VER` | `fe` | one byte; `fe` back means BROM, anything else is the preloader's version |
| `SEND_DA` | `d7`, address, length, signature length (each echoed, u32 BE) | u16 status (`0x1d0d` = SLA required) |
| | DA1 in 512-byte packets, a zero-length packet after every `0x2000` bytes and at the end, 120 ms pause | u16 checksum (XOR of the LE 16-bit words), u16 status |
| `JUMP_DA` | `d5` (echoed), address u32 BE | the address back, u16 status 0 |

On the X28, DA1 goes to `0x200000` (every logged session says "Jumping to 0x200000: ok"; none logged a checksum
warning in 14 sessions, so x28flash treats a checksum mismatch as fatal where mtkclient only warns).

Deliberately **not** sent: `GET_VERSION`, `GET_HW_SW_VER`, `GET_ME_ID`, `GET_SOC_ID` (mtkclient reads them for DA
selection and logging; x28flash pins the DA instead and avoids handling the unit's identity), and every register or
memory write (`WRITE16/32`, the watchdog sequence; the recovery scripts already ran with `--skipwdt`).

### DA loader file (`da.rs`)

`MTK_DA_v6` file: a 0x68-byte header, an entry count at `0x68`, entries of `0xDC` bytes from `0x6C`. Each entry:
magic, hw code, hw subcode, hw version, sw version, reserved, page size, reserved, entry index, region count, then
20-byte regions (`buf`, `len`, `start_addr`, `start_offset`, `sig_len`). Region 1 is DA1 (sent whole, signature
included), region 2 is DA2 (sent without its signature). For the pinned Quectel `DA_BR.bin` this gives DA2 =
`0x2db10` bytes at `0x40000000`, matching [RECOVERY.md](../RECOVERY.md#download-agent-erase-behavior-bounded-static-check-2026-10-28)
(a host test checks it when `X28FLASH_DA` points at the file).

The DA is sent **byte for byte unmodified**. mtkclient, seeing SBC off, runs its DA patchers; on this DA they matched
nothing ("not patched" warnings, no "Patched" lines), so what it sent was the same bytes.

### XML framing

Every packet is a 12-byte header (`0xFEEEEEEF`, type, length, all LE) then the payload, sent as two bulk
transfers. Type 1 is protocol flow; type 2 is a DA log line (4-byte priority + text) that may arrive anywhere and is
collected into `da.log`. Strings go out NUL-terminated, so mtkclient's `ack()` (`"OK\0"`) is the 4 bytes `OK\0\0`
and `ack_value(n)` is `OK@0x<n>\0\0`.

A command is: host XML -> DA `OK` (or `ERR!UNSUPPORTED`) -> data phase if any -> DA `CMD:END` with a result -> host
ACK -> DA `CMD:START` -> host ACK. A refused command still goes END -> ACK -> START, which x28flash follows so the
session stays in step. `CMD:PROGRESS-REPORT` replies are ACKed until `OK!EOT`.

### Session order

Same order as the unit's logged session, with the replies it got:

| Command | X28 reply | x28flash |
|---|---|---|
| (after JUMP_DA) `CMD:START` | | waits for it |
| `SET-RUNTIME-PARAMETER` (version 1.1, UART log, INFO, init DRAM) | `ERR!UNSUPPORTED` | sends, accepts the refusal |
| `HOST-SUPPORTED-COMMANDS` | `ERR!UNSUPPORTED` | same |
| `NOTIFY-INIT-HW` | `OK` | sends |
| `SET-HOST-INFO` (UTC timestamp) | `OK` | sends |
| `BOOT-TO` `0x40000000`, DA2 length | `OK`, then `CMD:DOWNLOAD-FILE` | uploads DA2 in `packet_length` pieces |
| `HOST-SUPPORTED-COMMANDS`, `NOTIFY-INIT-HW`, `CAN-HIGHER-USB-SPEED` | refused, `OK`, refused | sends |
| `GET-SYS-PROPERTY DA.SLA` | `ERR!UNSUPPORTED`, then mtkclient times out on an extra read | **skipped**: SLA is off in the target config, and the X28 patch treats the empty reply as off |
| `GET-HW-INFO` | NAND, page `0x1000`, block `0x40000`, spare `0x40`, total `0x3ff00000` | sends; stops unless the geometry matches and covers the layout |
| `EMMC-CONTROL LIFE-CYCLE-STATUS` | `OK` | **skipped** (eMMC only) |
| DA extensions (`CUSTOM`) | failed to build on this DA | **never sent** |
| `READ-FLASH NAND-WHOLE <offset> <length> ROM_0` | `OK`, `CMD:UPLOAD-FILE`, data | one per partition |

`READ-FLASH` data phase (mtkclient `download_raw`): DA `OK@<length>` -> ACK -> DA `OK` -> ACK, then per chunk:
data -> ACK -> DA status -> ACK. After the last chunk that status is the `CMD:END`, then `CMD:START`. x28flash checks
the announced length equals the request, every chunk fits, END says `OK`, and the byte count is exact.

### The four X28 patches, carried over

| mtkclient patch (`setup_mtkclient.py`) | x28flash |
|---|---|
| `check_sla()`: empty `DA.SLA` reply means off | the query is not sent; target config `0x0` is required instead |
| empty `page_parity_size` reads as 0 | the field is never parsed |
| `upload()`: no extra ACK after a raw upload | the upload ends with exactly one ACK for END and one for START; a test fails if an extra ACK is added (checked by mutation) |
| DA extensions skipped when they cannot be built | extensions do not exist in x28flash |

## Where the DA comes from

The working DA is Quectel's T750 `DA_BR.bin` (381,660 bytes, SHA-256 `c3d9058a…7d66d56`) from the community
package `spft-x28-nand-unlocked.zip` of [mt6890-cpe-recovery](https://github.com/mt6890-cpe-recovery/mt6890-cpe-recovery).
It is vendor code of unclear redistribution status, and its provenance is uncertain (it matches neither the
package's own `MD5SUMS.txt` nor the unsigned copy), so it is **never committed, embedded in the binary or attached
to a release**.

| Option | Verdict |
|---|---|
| **User points at the file** (`--da DA_BR.bin`), x28flash checks the pinned SHA-256 and refuses anything else | **Chosen** for phase 1. |
| mtkclient's bundled `MTK_DA_V6.bin`, fetched by pinned hash | Rejected: on this board it refuses `READ-FLASH`, `READ-PARTITION` and `READ-PARTITION-TABLE` (TESTING.md). |
| Download the community zip by pinned hash and extract `DA_BR.bin` | Possible later (`x28flash get-da`): no redistribution by us, but adds an HTTP and zip dependency and trusts a third-party release staying online. |

## Partition table

The DA cannot read one for this NAND (`READ-PARTITION-TABLE` is refused, and there is no GPT). The layout is the
unit's `/proc/mtd` (51 partitions back to back from 0, ending at `0x3fe80000`), compiled in as
`src/x28-mtd.txt`. Full USB reads matched the SSH backup by hash on these offsets twice (RECOVERY.md), which is the
proof that the layout is right. `--mtd` takes another unit's `/proc/mtd`, and `--backup` refuses a backup whose
`mtd.txt` differs from the layout in use. `GET-HW-INFO` must report 4 KiB pages, 256 KiB blocks and enough NAND.

## Safety rules, carried over

| Rule (CLAUDE.md, RECOVERY.md) | Phase 1 (read-only) | Write phase (future) |
|---|---|---|
| Read-only by default | A host test allowlists every DA command (8 setup/read commands) and preloader opcode (`fd d8 fe d7 d5`) in the source; anything else fails it (checked by injecting a `WRITE-FLASH`) | Writes behind a separate cargo feature or binary, so the released read-only binary cannot write |
| Only proven hardware | Refuses hw code other than `0x992`, BROM mode (untested here), any boot security on, any DA other than the pinned one, a NAND geometry that does not fit | Same, plus the unit binding the Python sessions use (layout hash, `proinfo` hash) |
| Full verified dump first | `dump` writes `images/` + `SHA256SUMS`; `verify` re-hashes; `--backup` compares with the SSH backup | A write refuses to start without a complete, verified dump of this unit taken by the same tool, bound by hash |
| Inactive slot only | n/a | The slot that is **not** `bootslot` in `/proc/cmdline`, checked live (the native image runs from A today, so A is not automatically the target); never the preloader, `misc` or NV partitions |
| `misc` never over the DA | n/a (reads are fine) | `misc` block writes were never acknowledged; it stays out of x28flash entirely |
| Dry run | Every step before USB contact runs offline (DA check, layout, backup compare) | Dry run is the default and needs no device |
| Typed confirmation | A confirmation prompt before any USB contact (`--yes` skips it; nothing is at stake) | A typed phrase naming target, image hash and unit, per step, as `slot_entry.py` does |
| Verify after write | n/a | Read back target and neighbour guards in the same session; one write, no automatic retry |
| Rehearsal and receipts | n/a | As `slot_entry.py`: an `identical` rewrite must pass before `write`; a `restore` mode with the wider restore guards; a journal fsync'd before USB I/O; receipts bound to unit (`proinfo`), host, the tool binary's hash, DA and layout hash and image, expiring after 24 h, never used to resume except by `restore` |
| Preconditions | n/a | UART capture, stable power, no FOTA, a second verified backup copy, A's tries at 0, base/candidate from the `package_ubi` manifest (`base_head`) |
| NAND specifics | n/a | Writes aligned to 256 KiB erase blocks; how `NAND-WHOLE` raw offsets meet bad blocks/BMT must be settled first |
| Way back | Power-cycle; nothing changed | Proven restore of the original bytes before the write is offered |
| A/B boot tries | See below | See below |

### Boot tries: the rule that applies even to reads

The preloader adds one try to slot A per boot and `x28-bootok` resets it after a good boot (TESTING.md 27). Stock B
**erases A** if B ever boots with A's tries above 3. Whether a power cycle that stops in USB download mode also adds
a try is **unknown**. So every x28flash session, read-only included, must follow:

1. Before: the unit booted A normally and `x28-bootok` reset the counter (tries 0; check with the `dd` command in
   TESTING.md 27).
2. One USB session, then power-cycle and let A boot fully; confirm tries are back to 0 before another session.
   `dump` enforces part of this: it reads `misc` first, saves A's tries from all four copies in `misc-tries.txt`,
   and stops if any copy is 2 or more (1 may be this session's own power-on). `detect` says the power-on may have
   counted.
3. Never chain sessions without a good boot in between. A session that dies mid-way is still a session.

The first hardware run can settle the unknown read-only: check tries over SSH (0), run one `dump --only misc`, and
read `misc-tries.txt` (the tries byte is `0x809 + n * 0x40000` in `misc` for copies n = 0..3, as in TESTING.md 27).
A 1 means the download-mode power-on counted.

## The UX

`x28flash` with no arguments opens a menu (back up everything / some partitions / detect / show layout / verify).
Subcommands: `detect`, `partitions`, `dump --da … [--only …] [--backup …]`, `verify DIR [--backup …]`. It waits
for a port that appears *after* it starts (an already-present port means a stale session, as mtkclient assumes),
shows a spinner while waiting and loading the DA, an overall progress bar with speed and ETA, ✔/✖ per partition
with MATCH/DIFF against a backup, and a summary that ends with "cycle the modem's power". Partial images are written
as `.part` and renamed only after a complete, exact-length read. The output folder must not exist and is created
`0700`. A failed `READ-FLASH` stops the session (its state is unknown) and keeps the finished images.

Build from source with `cd tools/x28flash && cargo build --release` (current stable Rust); CI artifacts are the
ready-made binaries.

## Tests

`cargo test` (host only, 23 tests): byte-exact handshake/identify, `SEND_DA` chunking, zero-length packets and
checksum, SLA refusal uploads nothing, XML framing and ACK bytes, refused-command resync, DA log packets, DA2
upload without the extra ACK, `GET-HW-INFO` with the empty parity field, `READ-FLASH` streaming and its failure
cases, the whole boot sequence against the logged order, loader parsing with bounds, the X28 layout, reading A's
tries from `misc`, and the read-only allowlist. CI (`.github/workflows/x28flash.yml`) runs the tests and clippy, then
builds release binaries for macOS arm64/x86_64, Linux x86_64/arm64 (static musl) and Windows x86_64.

## Hardware test plan for phase 1 (needs the owner)

Each step is one session under the boot-tries rule, the owner puts the modem in download mode by power-cycling, and
any failure stops the plan:

1. `x28flash detect`: handshake and target config only, no DA.
2. `x28flash dump --da … --only lk_b --backup <verified backup>`: expect MATCH (`0ad94f06…`).
3. Step 2's `misc-tries.txt` already settles whether download mode adds a boot try (above).
4. `x28flash dump --da … --backup …`: all 51; expect MATCH except the partitions written at runtime.

## Not verified

- Anything on hardware: nusb claiming the port on macOS/Linux/Windows, the handshake timing, the DA boot, reads,
  speed (mtkclient managed about 0.6 MB/s), and a full 1 GiB session (a single 1 GiB `READ-FLASH` once died after
  236 MiB; x28flash reads per partition as `read_all.py` does, so `user_data` is still one 427.5 MiB read. Splitting
  it into 64 MiB reads would lower the cost of a dead session, which is one more power-on, but departs from the
  proven path; decide after the first hardware run).
- Whether the skipped commands (`GET_HW_SW_VER`, `DA.SLA`, `EMMC-CONTROL`) are needed by this preloader or DA.
- The `READ-FLASH` per-chunk status is inferred from mtkclient's code, not from a traffic capture.
- Windows without WinUSB; BROM mode; other X28 firmware builds.
