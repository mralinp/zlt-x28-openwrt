# Changed-data restore: offline proposal (#62)

Prepared 2026-10-28 after the [first identical rewrite](first-write-plan.md#observed-execution-2026-10-28-57--60).
**Not ready to execute.** This document authorizes no write, power cycle, slot switch or SDK image.
The user has one unit and accepts replacement risk; calibration/identity loss remains a separate risk.

## Objective and exact candidate

Prove that known programmed bytes can be restored to their original erased value, with exact target
and guard reads. Do not induce a signature failure or boot altered data. The selected target remains
`rootfs_sig_a`, mtd28, main-data range `[0x13500000, 0x13600000)`, length `0x100000`.
Use this unit's original source and the same verified DA named in the first-write plan.

A host-only check of the original backup confirms partition-relative `[0x40000, 0x41000)` is
4,096 bytes of `0xff`. Candidate staged data replaces **only** that page with `aa 55` repeated
2,048 times. Full-partition images are used; this is not a partial-page or OOB write proposal.

| Image | SHA-256 |
|---|---|
| Original | `1ebb121adfbac5603dca0e65c3b276a315fda1450bdbd573f3c600b5f399d4b6` |
| Candidate staged | `20f35f4368ca7bc1447b459d92e1aacb759245b983cd102f28f524e025972e90` |

The candidate changes exactly 4,096 bytes at absolute `[0x13540000, 0x13541000)`.
It preserves both certificate structures and every other byte. Restoring these programmed zeros to
ones requires erase semantics somewhere in the storage path; a matching restored read establishes
that result, rather than proving an implementation's precise erase algorithm.

**Limit:** erased padding is an observation in this backup, not a documented writable scratch area.
It has not been proved that every vendor consumer ignores that page. Do not boot or invoke an upgrade
with the candidate present. The SDK belongs to another modem and must not supply replacement images.

## Gates and bounded sequence

1. Apply the merged #60 installer patch to the private host installation, preserve the previous host
   library, verify the exact single patch and rerun the actual-method offline regression. A merge does
   not update the installed SDK. No hardware action is needed for this gate.
2. Independently review and separately approve a single original-to-original rewrite using the patched
   host, with the original six pre/post reads, UART and normal B-return conditions from the first plan.
   Require successful **same-session** reads. Any protocol failure stops progression; fresh-session
   matches may establish the baseline but do not validate the patched completion path.
3. Build and host-test a separate bounded test/restore operation before staging any changed bytes.
   Keep the existing identical-only checker unchanged. The new operation must be limited to this
   exact target, original hash and one staged hash, with the original five guard identities. It must
   reject arbitrary source files, ranges and unexpected target contents.
4. Verify originals, full backup, DA, tool identity, disk space, B selection and full layout again.
   Preserve a verified copy on separate physical storage, or explicitly review that unmet gate.
   The existing second archive is on the same Mac. Require UART capture and review of pending update
   state. Known source identities do not establish bad-block handling or a damaged-preloader route.
5. Obtain approval for the exact changed-data session: at most **two host write requests**, first the
   candidate and then the original, with exact target and all five guard reads before staging, after
   staging and after restoring. These reads are 101 MiB per pass. No automatic reboot or slot switch.
   Keep the original immutable and independently hashed throughout. Stage acceptance requires both
   a successful DA acknowledgement and exact staged hash/length plus unchanged guards.
6. Only after all staging checks pass, perform the planned original restore once. Require successful
   acknowledgement, exact original target hash/length and unchanged guards. A successful restore
   allows a separately approved normal B return with UART and read-only SSH confirmation.

The five guards and their exact hashes/ranges remain those in the first-write plan: `boot_a`,
`rootfs_a`, `rootfs_sig_b`, `misc`, `boot_para`. They detect some collateral changes; they cannot
prevent damage or cover the entire NAND. Never relax a guard to make the experiment continue.

## Failure handling must exist before staging

Any short/failed read, false write acknowledgement, exception, guard change or unexpected target hash
stops the automatic sequence. No blind retry, unplanned erase, Linux `mtd write`, stock upgrade helper,
slot-A boot or normal reboot recommendation. Preserve UART/host logs and power/recovery state where
safe, then review the actual evidence.

A separate **restore-only entry** must be implemented and tested before staging. It may accept only
the exact staged target with every original guard matching, and write only the verified original once.
It must work in an already running DA session or a freshly reviewed DA entry without requiring Linux
SSH while the device is in recovery. B selection/layout must have been captured before entry and
slot metadata must be read again; define how that evidence is bound to this particular run.
Do not turn missing SSH into permission to ignore selection checks.

An unexpected target hash is not silently accepted even by restore-only mode: it needs a newly
reviewed recovery action. Thus this proposal is still not a universal damaged-partition recovery tool.
Power loss or protocol failure can strand the candidate; the active B slot reduces risk but its safe
boot under every failure condition is not established. Independent safety review and all failure-path
host tests are prerequisites, not work to defer until after the first changed write.

## Acceptance and explicit exclusions

Record the exact source hashes, tool revision, installed patch identity, write count, acknowledged
commands, all read lengths/hashes, UART observations and final slot. Publish only sanitized findings;
keep raw captures and vendor SDK local. A pass establishes restoration of this page on this unit in
this controlled session. It does not validate arbitrary images, NAND OOB/bad-block remapping, slot-A
boot, signature/content enforcement, fallback after failed verification, or preloader recovery.

This plan has only received manual offline review. Independent safety review was unavailable when
#61 was prepared and must be obtained before hardware execution. No runnable write command is supplied
until the scoped tool and its failure checks exist.
