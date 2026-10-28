# Selecting slot A and getting back to B (#92)

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
