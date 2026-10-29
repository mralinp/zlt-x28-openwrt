# First native image: write, select, recover (plan for #90)

**Plan only. It authorizes no write, power cycle or slot change.** Every step below needs its own explicit
approval, the tools it names do not exist yet, and the image is still **NOT-FLASHABLE** until the gates
at the end are closed. Built from [#91](content-enforcement.md), [#92](slot-selection.md),
[#87 guard](../BUILD.md#boot-path-guard-against-flash-and-other-slot-writes-87),
[#88](overlay-policy.md) and the proven [#72](changed-page-restore-result.md) engine.

## Order is the safety property

Slot selection lives in `misc`, which still says B. So:

1. **Write `rootfs_a` first.** Nothing boots A, so the unit keeps starting stock B whatever A contains,
   including after an interrupted write. A bad or half-written `rootfs_a` is harmless until step 3.
2. Verify `rootfs_a` by full readback hash; restore if it differs.
3. **Only then** write the four `misc` copies to select A, as a separate approved session.
4. Boot A under UART. Return path = automatic fallback (inferred) or restoring `misc`.

`rootfs_sig_a` and every other A partition stay untouched: it already carries the valid stock certificates
(#91), and the stock B-side `ab_image_sync "_a"` repair (#92) is not triggered while A's retry counter is 0. The repair condition is `retry_a > 3` seen from B (`zmtk_boot_done:137-142`); what the counter reads after a preloader rollback is unobserved, so after any fallback assume stock B **may** have copied B over A.

## Target facts (read-only, 2026-10-29, stock B)

| Item | Value |
|---|---|
| `rootfs_a` | mtd29, `0x04000000` (64 MiB), erase block 256 KiB, page 4 KiB, OOB 64 |
| Bad blocks / ECC failures | `rootfs_a` 0 / 0, `misc` 0 / 0, `rootfs_b` 0 / 0 (`/sys/class/mtd/*/bad_blocks`, `ecc_failures`) |
| Engine range for `rootfs_a` | `[0x13600000, +0x4000000)` |
| Current content | original SHA-256 `5f0c997d...` (the backup `mtd29-rootfs_a.bin`) |
| Candidate | `rootfs-a-experimental.bin`, 64 MiB, 44 populated PEBs, rest `ff`; per-build digest in its manifest |

With no bad blocks, the physical block `n` of the image is the block `n` the UBI attach expects, so no
bad-block remapping is needed. The engine has no bad-block check; a bad block would surface only as a readback mismatch. Re-read `/sys/class/mtd/mtd29/bad_blocks` (read-only SSH) immediately before the write.

## Status of the tools

`tools/recovery/slot_session.py` (this repo, host-tested with a fake DA) is the **engine** for both
sessions below: fixed target, original/candidate hash binding, per-spec candidate validator
(`rootfs_a`: different 64 MiB image that passes `package_ubi.inspect`; `misc`: exactly the four-copy
A selection), neighbor guards re-read before and after, one write, no retry/reboot, restore tolerant of a
half-written target. Checked against the real private candidate and `misc` dump. **Entry command (`tools/recovery/slot_entry.py`, built):** `slot_entry.py {rootfs_a|misc} {identical|write|restore}`.
Dry-run is offline. `--write` additionally needs `--backup-copy` (a second, verified archive), `--uart-log` (updated within
60 s), live SSH confirming B, 1 GiB free, the pinned DA/host/tool/unit identities, and a typed phrase that names the
target, mode, the first 12 hex digits of the image, `SAME-DISK` when the copy shares a disk, and for `misc` also
`BROM-ROUTE-PROVEN`. Every session needs `--candidate-dir`: the rootfs_a hash comes from that `package_ubi` manifest (never from a receipt), is checked against the image bytes, and is part of every receipt's identity, so a `misc` session can only select the exact approved `rootfs_a`. The `misc` phrase names both images (`WRITE write misc cd512c873dd4 ROOTFS-A <12 digits> BROM-ROUTE-PROVEN`); `identical` and `restore` phrases name the original that will land. The candidate validators and the host check run before any connection or claim, every prior (including a verified one) is spent once claimed for restore, and receipts must match the journal's target, offsets, written hash and acknowledgement. The tool hashes include `build/package_ubi.py` and `stage_native.py`: **freeze the tools once a write has happened**, or the restore receipt will not match. Sequencing is enforced by receipts: `rootfs_a write`
needs a verified `identical` run (24 h); `misc identical` needs a verified `rootfs_a write`; `misc write` needs both a verified
`misc identical` and that `rootfs_a write`; `restore` needs `--resume` of the stopped or finished write run and is claimed once.
**Not done:** hardware identical-write passes, a proven BROM route, and the router-safety-auditor's review of the entry
command. No device I/O has been run through it.

## Reflash from a named base image (#137, owner-approved relaxation)

After the first native image is on `rootfs_a` and `misc` selects A, `slot_entry.py rootfs_a {identical|write|restore} --base-dir <package_ubi output now on rootfs_a>` starts `identical`/`write` from that pinned base instead of the stock original. Differences from the default flow, only in this mode: `misc` must be **unchanged during the session** (it is never written here) instead of equal to the B-selected record; the live SSH check must confirm **A** instead of B; the phrase and receipt identity name the base (`BASE <12 hex> MISC-SELECTS-A`). `restore` still writes the stock original over any state. Everything else (neighbor guards, receipts, one write, no retry or reboot) is unchanged. The risk accepted: if the write fails, `misc` selects a broken A, so recovery is the DA `restore` route, not a B fallback.

## Step 1: `rootfs_a` write session (tool to build: #99)

A new bounded session next to `changed_restore.py`, with the same shape: no connect/retry/reboot options,
a hash allowlist of exactly **two** sources (original `5f0c997d...` and the one candidate), target fixed to
`rootfs_a`, journal fsynced before each USB write, `STOP` on the first discrepancy.

- Guards read before, after the write and after any restore: `boot_a`, `rootfs_sig_a`, `rootfs_sig_b`,
  `misc`, `boot_para` (the #72 set with `rootfs_sig_a` swapped in for `rootfs_a`) plus `lk_a`/`tee_a`.
- Modes: `identical` (original over original, to prove the 64 MiB path first, like #70), `test`/`write`
  (candidate), `restore` (original). Re-entry after an abort is restore-only, as in #67.
- Verification: whole-partition readback SHA-256 of the candidate, plus the independent UBI inspection
  of the readback with the build tooling (`package_ubi.inspect`) against the build manifest.
- Cost: reads are 64 MiB per check; budget three passes plus guards, and run the identical-write rehearsal
  first. Wear is a few erase cycles on a partition that A/B repair already rewrites.

## Step 3: `misc` selection session (tool to build: #100)

**`misc` is its own risk class.** The engine writes the whole 1 MiB partition (four 256 KiB erase blocks), as the
proven `rootfs_sig_a` session did, but `misc` is the live selector: a power or USB loss mid-write can leave blank or
mixed slot records that the preloader may refuse (`no valid slot!`) or read unpredictably. Even the identical-data
rehearsal carries this risk, so it is not a free dry run, and it must not be done before a BROM route is proven
(gate 6). The four changed ranges are `0x800 + k * 0x40000`; source allowlist = the verified dump
(`d8a5b852...`) and the one A-selected image (derivation and bytes in #92: per copy `0e000100 0f000100` →
`0f030000 0e000100`). Guards: `rootfs_a` (exactly the candidate hash) and every A and B counterpart (`boot`, `lk`, `tee`, `rootfs_sig`, `rootfs_b`) plus `boot_para`. The candidate hash is pinned in the spec (`cd512c87...`).
Identical-write hardware pass on the original `misc` before any changed write. `restore` writes the original.

## UART and expectations

1.8 V logic, shifted RX only, 921600 8N1, common ground, log to a private file *before* the first write
(the proven setup from #51). On the first A boot expect, in order:

| Log | Meaning |
|---|---|
| `slots[0].priority:15 ... slots[1].priority:14`, `ab_suffix: _a, ab_retry: 3, ab_boot_success: 0` | selection worked |
| `ROOTFS_SIG_VFY Success`, `bootslot=a`, `ubi.mtd=...` | LK accepted the unchanged certificates |
| UBI attach, SquashFS mount, procd, `x28-switch` quiet, no `/tmp/x28-switch.failed` | the image runs |
| `ab_retry` falling on each failed boot, then `ab_suffix: _b` | fallback to B (inferred; this run observes it) |

## Failure matrix

| Observation | Meaning | Action |
|---|---|---|
| Hang before `Starting kernel`, `ROOTFS_SIG_VFY Fail` | a content/signature consumer exists | power-cycle up to the try budget; restore `misc` if B does not return |
| Kernel panic or mount failure | image problem | same; fix the image, rebuild, rewrite |
| A runs, no SSH on 192.168.70.1 | switch/management problem; no UART shell (no getty, failsafe removed) | let tries run out, or restore `misc` |
| Boots B again after 3 tries | fallback works | record it; keep the log |
| Neither slot boots | the matrix failed | BROM/DA restore from the verified backup: **the only route independent of boot, and not yet tested on a unit that cannot boot** |

## Restore order and post-fallback state

- Once `misc` selects A, restoring `rootfs_a` is refused by the engine (its `misc` guard fails). The order is always
  **`misc` first, then `rootfs_a`**.
- After a fallback, `misc` restore tolerates `rootfs_a` being the candidate, the original, or a copy of B (stock
  repair), and nothing else; every other guard must still match exactly.
- The first A boot has a **UART shell** (#104): `ttyS0::askfirst:/bin/ash --login` at 921600 8N1, press Enter on
  the proven shifted-TX/RX setup. It needs the board's UART pads (physical access), root's password stays locked and
  SSH stays key-only. It is the way in if switch/network init fails, since failsafe is removed and there is no getty.
  Unverified on hardware: that procd creates `/dev/ttyS0` (stock does the same with `getty -L ttyS0`) and that
  the prompt appears. If it does not, the boot is kernel-log only and the three-try fallback is the exit.

## Gates before the first write (all must be true)

1. #86, #87, #89 merged; #88, #91, #92 merged; the new tools (#99, #100) merged with host tests and a
   hardware identical-write pass each.
2. Router-safety-auditor sign-off on this plan and both tools.
3. `rootfs_a` and `misc` originals re-hashed against the backup, and **a verified second copy on separate
   physical storage** (done 2026-10-29: a USB drive, SHA-256 `84ad2ad8...` identical to
   `ARCHIVE.sha256`; pass it as `--backup-copy`, so no `SAME-DISK` token is needed while it sits on that drive).
4. UART capture running; read-only preflight shows B selected, no pending FOTA/slot operation.
5. The attested entry command exists (pins the build-manifest hash, receipts, UART log, typed confirmation).
6. The recovery route is **proven** as set out in [recovery-route-proof](recovery-route-proof.md) (the auditor's finding: all DA work so far ran on
   a booted stock-B unit), and a 64 MiB identical `rootfs_a` rehearsal has passed.
7. `zmtk_boot_done` on B has been re-read read-only for the fallback behavior, and the owner has decided whether
   B's `ab_image_sync` must be blocked.
8. The user approves the exact target, source hash, one write request per session and each power cycle.

The fallback to B is **expected, unverified**.

Not covered: secure-world enforcement (#91), the unobserved preloader retry logic (#92), mixed `misc`
copies after a power cut.
