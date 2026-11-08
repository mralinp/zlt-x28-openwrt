# Selecting slot A and getting back to B (#92)

> **Correction (2026-11-09, #302):** the preloader's limit is 6 tries, not 3, and it reads the first of the four copies whose magic matches. See [slot-b-reuse](slot-b-reuse.md).

Offline, 2026-10-29: stock upgrade scripts in `rootfs-b-system.tar.gz`, strings of the preloader
(`mtd00-preloader.bin`) and `lk_b`, the verified `misc` dump, and the [UART log](uart-boot-log.md).
Nothing was run on the router and no record was written. **This is a plan with an unverified
fallback assumption, not an approved operation.**

## Who decides

The **preloader** decides the slot. Its strings include `[QL_AB] metadata.slots[0].priority`,
`[AB] ab_suffix: %s, ab_retry: %d, ab_boot_success: %d`, `ab_switch_boot_part`, `rollback_slot fail`,
`no valid slot!` and `[QL_AB] set retry count failed`; the UART log shows them before LK starts. LK only
turns the chosen suffix into `bootslot=a|b` and `ubi.mtd=28|42` (`ql_raw_data_module.c`), and answers
"set active slot" with `not supported!`, so LK offers no switching API. The preloader's code was not
disassembled: its retry/rollback behavior below is inferred from strings and the stock scripts.

## The record

`misc` is exactly 1 MiB (four 256 KiB erase blocks), every byte after the records is `ff`. The same
16-byte record sits at `0x800`, `0x40800`, `0x80800`, `0xc0800`:

```text
00414230 ffffffff | A: 0e 00 01 00 | B: 0f 00 01 00      priority, tries, success, up-type
```

The vendor writes single bytes with no checksum, so none exists to update (`set_bootctrl` in
`lib/upgrade/bootctrl.sh` replays one byte at `offset + 256 KiB * i` for i = 0..3).

## The vendor's own switch recipe, replayed on this state

`change_slot_info "_b"` (run from B after the new image is in A, up-type 0) writes
`set_bootctrl_string 1 0f 1 03 1 00 1 00 1 0e 0 00 0 00 0 00`, that is: A priority `0f`, A tries `03`,
A success `00`, A up-type `00`, B priority `0e`; other B bytes untouched. Result:

```text
before  00414230ffffffff 0e000100 0f000100
after   00414230ffffffff 0f030000 0e000100
```

Four bytes change in each copy (`+8` 0e→0f, `+9` 00→03, `+10` 01→00, `+12` 0f→0e), in all four erase
blocks. **Reversal** is the original 16 bytes (`misc` SHA-256 `d8a5b852...`); the vendor's inverse is
`change_slot_info "_a"`, which sets B priority `0f`, B tries `03`, B success `00`, A priority `0e`.
Priority alone orders the slots; tries and success are what the preloader's retry logic uses.

## Consequences of that recipe

1. **Probable automatic fallback.** A at tries 3 / success 0 means the preloader (inferred) spends a try
   per boot and rolls back to B when they run out. B keeps success 1 and priority 14, so an A that never
   confirms should return to stock B after three boots. This is the dead-man switch the first boot should
   rely on, and it is **unverified**: UART must show `ab_retry` falling and `ab_suffix: _b` returning.
2. **A is never confirmed.** The image has no `zmtk_boot_done` (#87), so success stays 0. A working A also
   reverts to B after three boots. Confirming A needs a reviewed `misc` write from OpenWrt, deliberately
   deferred past the first experiment.
3. **Stock B repairs A on fallback.** `zmtk_boot_done` (lines 124-141) runs `ab_image_sync "_a"` when it
   sees A's retry above 3, overwriting our `rootfs_a` (and every other A partition) with B's. That is
   recovery for free, and it also erases the experimental image and any on-flash evidence. Capture UART
   and copy any needed file off the device before relying on A's state.
4. **Writing `misc` is the missing tool.** The recovery tools deliberately deny shared `misc` writes.
   Writing it live with the vendor `dd-nand` helper is a read-erase-write of a 256 KiB block per copy; a
   power loss mid-write damages one copy. The route already proven on hardware is the bounded
   changed-page engine ([#72](changed-page-restore-result.md)); it is extended to `misc` as a whole-1-MiB session (`slot_session.py`), a higher risk class because `misc` is the live selector; the bytes that change are four per copy
   plus their restore, with its own offline tests and a hardware pass on identical data first.

## Gates this leaves for #90

- Extend the bounded engine to `misc` (whole partition, restore from the verified dump), host tests, identical-write
  hardware pass.
- UART capture running; expected lines: `ab_suffix: _a, ab_retry: 3, ab_boot_success: 0` on the first
  A boot, then `_b` after exhaustion.
- Know that a power cut between the four `misc` copies leaves mixed records; the preloader's choice among
  mismatched copies is unknown.
- No unconfirmed claim of fallback may appear in the PR that flashes: it must say "expected, unverified".

## Swapping which slot boots, from the running system (X28 PRO, 2026-11-07)

`misc` is a 1 MiB partition (`mtd3`, flash offset `0x700000`) of raw bytes, not a file system: four identical copies of the 16-byte
record above, one per 256 KiB erase block. The preloader reads it at every power-up and boots the slot with the higher priority
(`0f` over `0e`). It cannot be written over USB (TESTING 28, reproduced on this unit with a purpose-built tool: the first block write
was not acknowledged and the download agent then stopped answering until a power cycle), so it is changed from the running system with
the stock `dd-nand`, which the native image ships in `/sbin`.

The X28 PRO unit's record before the change, after a flash of the native image to slot A (checked over SSH with
`dd if=/dev/mtd3ro bs=4096 count=1 | dd bs=1 skip=2048 count=16 | hexdump -C`):

```text
00414230 ffffffff | A: 0f 00 00 00 | B: 0e 00 01 01      A first; B good (success 1, flag 1)
```

A's tries are 0 and its success 0 because `x28-bootok` writes the tries byte back to 0 once the system is up (TESTING 27), not because the
tries ran out: the unit booted slot A (`bootslot=a`) with exactly this record, so a slot with tries 0 and success 0 boots when it has the
higher priority. Priority alone chose it.

To boot slot B (the vendor firmware) only the two priority bytes change; tries, success and flags stay as they are. For each copy
`k` = 3, 2, 1, 0 (last to first, so copy 0, the one the preloader most likely reads first, still says "boot A" if anything stops early),
with `off = 2048 + 262144 * k`, one call rewrites A's four bytes and B's priority together, so no copy ever holds two equal priorities:

```sh
printf '\x0e\x00\x00\x00\x0f' | dd-nand of=/dev/mtd3 seek=$((off+8)) bs=1 count=5
dd if=/dev/mtd3ro bs=1 skip=$((off+8)) count=8 | hexdump -v -e '1/1 "%02x"'    # expect 0e0000000f000101
```

Result: `A: 0e 00 00 00 | B: 0f 00 01 01` in all four copies, read back after each; the whole 1 MiB compared with the saved copy differs in
exactly 8 bytes (`0x808`, `0x80c` in each block). Save the whole partition first (`cat /dev/mtd3ro > misc.bin`, sha256 before:
`9aaf725e...`); the undo is the same call with `\x0f\x00\x00\x00\x0e`. Each call is a read-erase-write of one 256 KiB block, so
the unit should be on stable power. Do not run `dd-nand --help`: it waits for input.

Observed: after a power cycle the unit booted slot B (`bootslot=b`, OpenWrt 19.07-SNAPSHOT, the vendor firmware) and the key-only SSH on
port 2222 from `x28-flasher#5` answered (`ssh -p 2222 -i ~/.ssh/router root@192.168.0.1`); `misc` still read
`A: 0e 00 00 00 | B: 0f 00 01 01`. The way back to slot A is the same call with the two priorities exchanged (`\x0f\x00\x00\x00\x0e`).
