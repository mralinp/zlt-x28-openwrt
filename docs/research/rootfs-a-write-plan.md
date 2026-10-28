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
(#91), and the stock B-side `ab_image_sync "_a"` repair (#92) is not triggered while A's retry counter is 0.

## Target facts (read-only, 2026-10-29, stock B)

| Item | Value |
|---|---|
| `rootfs_a` | mtd29, `0x04000000` (64 MiB), erase block 256 KiB, page 4 KiB, OOB 64 |
| Bad blocks / ECC failures | `rootfs_a` 0 / 0, `misc` 0 / 0, `rootfs_b` 0 / 0 (`/sys/class/mtd/*/bad_blocks`, `ecc_failures`) |
| Engine range for `rootfs_a` | `[0x13600000, +0x4000000)` |
| Current content | original SHA-256 `5f0c997d...` (the backup `mtd29-rootfs_a.bin`) |
| Candidate | `rootfs-a-experimental.bin`, 64 MiB, 44 populated PEBs, rest `ff`; per-build digest in its manifest |

With no bad blocks, the physical block `n` of the image is the block `n` the UBI attach expects, so no
bad-block remapping is needed. A new bad block appearing during the write must stop the session.

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

Same pattern for `misc` only: four 4 KiB pages at `0x800 + k * 0x40000`, source allowlist = the verified dump
(`d8a5b852...`) and the one A-selected image (derivation and bytes in #92: per copy `0e000100 0f000100` →
`0f030000 0e000100`). Guards: `rootfs_a` (candidate hash), `rootfs_sig_a/b`, `boot_a/b`, `boot_para`.
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
| Neither slot boots | the matrix failed | BROM/DA restore from the verified backup, the only route independent of boot |

## Gates before the first write (all must be true)

1. #86, #87, #89 merged; #88, #91, #92 merged; the new tools (#99, #100) merged with host tests and a
   hardware identical-write pass each.
2. Router-safety-auditor sign-off on this plan and both tools.
3. `rootfs_a` and `misc` originals re-hashed against the backup, **and a verified copy on separate physical
   storage** (the existing archive is on the same Mac).
4. UART capture running; read-only preflight shows B selected, no pending FOTA/slot operation.
5. The user approves the exact target, source hash, one write request per session and each power cycle.

Not covered: secure-world enforcement (#91), the unobserved preloader retry logic (#92), mixed `misc`
copies after a power cut.
