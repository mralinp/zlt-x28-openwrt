# Changed-data restore: offline proposal (#62)

Prepared 2026-10-28 after the [first identical rewrite](first-write-plan.md#observed-execution-2026-10-28-57--60).
**Historical proposal; executed under separate approval in [#72](changed-page-restore-result.md).**
This document itself authorizes no write, power cycle, slot switch or SDK image.
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

## Offline engine implementation (#64)

`tools/recovery/changed_restore.py` implements the bounded session sequence, with no CLI or hardware
imports. `test` accepts only the original target, stages the exact candidate once, verifies all six
partitions, restores the original once and verifies all six again. `restore` accepts only the exact
staged target and original guards before its single original-image write. Every source identity,
acknowledgement, length and hash is checked. Any exception or mismatch stops; there is no retry,
connection close, automatic reboot, or slot switch. The caller retains recovery state for review.

Each invocation creates a private run directory with separate readbacks, source snapshots and a
flushed journal recording attempted writes before USB calls. A journal is evidence, not a resumable
approval token. Sources and captures must remain under ignored private storage when used later.
Host tests use synthetic data and a fake DA; no vendor SDK or USB dependency is needed in CI.

**Engine-only scope (#64):** this engine takes an already established DA session. The guarded
entry command below (#66) adds pre-entry slot/layout binding, selection-metadata checks and host/DA
validation. Do not call the engine manually on a live DA to bypass those gates. The existing
identical-only checker is unchanged. Offline tests do not prove recovery on the device.

## Guarded entry command (#66)

`tools/recovery/restore_entry.py` supplies `identical`, `test` and `restore` entry modes.
Default is an **offline dry-run**: it verifies local originals, all 51 backup images, exact full
layout, DA hash and installed XML implementation, but performs no SSH, hardware import or USB I/O.
The installed XML file must equal `git show` of the pinned upstream blob plus the reviewed installer
patches; a dirty checkout or matching version label alone is insufficient. The current private
installation was detected as unpatched by this preflight; it was not modified during implementation.

After merging and independently reviewing this command, apply the installer host patch and rerun
all host checks before requesting approval for the next identical write. No fresh device operation
has been approved or performed by this PR. The following templates are **for review**, not execution:

```sh
python3 tools/recovery/restore_entry.py identical
# Later, only with separate approval and the correct private capture/copy paths:
# private/mtkclient-7cb40e7/venv/bin/python tools/recovery/restore_entry.py identical \
#   --write --backup-copy /verified/copy/complete-captured-partitions.tar --uart-log /private/live-uart.log
```

`--write` requires the private venv interpreter (re-exec occurs before hardware import), a verified
second complete archive, at least 768 MiB free, a nonempty UART log updated within 60 seconds,
and exact typed confirmation for this mode and target. A hard link to the original archive is refused.
Same-filesystem copies require the additional `SAME-DISK` confirmation and record the unmet physical
backup protection; different filesystem IDs also do not by themselves prove separate physical storage.
The operator must review that storage risk and attest continuous RX capture, stable power and no
pending stock upgrade/FOTA. A recent log timestamp cannot establish capture wiring or guarantee future
logging. All these conditions require explicit review before execution, not a blanket unattended run.

Initial `identical` and `test` entry requires fresh key-only SSH confirming B and the entire fixed
layout before USB entry. A private receipt fingerprints source, DA, installed host library, actual
local implementation files and this unit's backup `proinfo` hash. It records the canonical run path,
mode, pre-entry B selection, timestamp, archive-copy condition and journal digest. No password is used.
After connection, a fresh exact-length/hash DA read of `proinfo` binds the device to that unit; the
actually imported XML module must match the verified implementation. The engine then reads the target
and every fixed guard, including `misc` and `boot_para`, before any write. Matching those full metadata
partitions binds the runtime selection state to the previously reviewed B baseline; it does not predict
later stock boot or upgrade behavior. Receipts cannot replace those fresh reads.

`identical` writes the original once and requires all six exact same-session post-read matches.
`test --prior-identical ENTRY_RUN` requires that matching tool/unit/source/DA receipt, successful
write acknowledgement and the full twelve-read journal, unchanged and no older than 24 hours.
The test receipt retains the canonical rehearsal run reference for traceability.
The prior receipt is evidence, not approval of changed-data testing. A separate exact-mode confirmation
is still required. Test mode retains the two-write maximum from the plan.

`restore --resume FAILED_TEST_ENTRY_RUN` bypasses SSH only for a bound stopped test run whose durable
journal records exactly one staged-write attempt and no original-write attempt. It still checks all
local identities, copy/log/space conditions, fresh unit identity, exact current staged bytes and every
original guard. It atomically creates an exclusive one-use claim in the failed run before connecting, preventing an
automatic retry with the same receipt. A restore attempt that itself fails, an unknown target, or a
changed guard requires a separately reviewed recovery action. No generic damaged-target override exists.

**Interruption limit:** SIGKILL, host power loss or a full/broken log filesystem may leave no complete
terminal receipt/journal. This command intentionally refuses that evidence. It cannot promise recovery
from every interruption; a separately reviewed action using fresh reads is required. There is no stale
receipt timeout on stopped-test recovery, but exact current state and new explicit approval remain
mandatory. This is a local operator workflow, not an authenticated security boundary against someone
who can edit the code and private receipts.

All readbacks, source snapshots, chip/identity data and receipts stay in ignored `private/usb-probe`.
The command closes only its host USB handle, never requests DA shutdown or reboot, and says STOP on
unverified outcomes. Normal B return remains a separately reviewed power cycle after all original and
guard reads pass, followed by UART and read-only SSH confirmation. At #66 preparation, hardware
validation remained outstanding; the #70 result below establishes identical-mode success only.

## Identical-mode prerequisite observed (#70)

The [patched identical-write test](patched-identical-write-result.md) now passes on hardware:
one original-byte write, all twelve same-session target/guard reads, independent file rehashing,
and UART/SSH-confirmed stock-B return. The host patch is installed and all 63 recovery tests pass.
No `test` or `restore` mode was executed. The changed-data operation still needs fresh preflight,
UART/copy/storage review, independent safety review and separate exact-scope approval. Its prior
receipt must match current implementation/unit identities and the 24-hour window; a documentation
merge does not grant approval or relax those checks.

## Changed-page test completed (#72)

The separately approved [hardware result](changed-page-restore-result.md) is PASS: exact candidate,
all staging guards, original restore and all final guards verified, followed by stock-B return.
Two acknowledged writes and eighteen same-session exact reads were independently checked. This
supersedes earlier pending-status statements for the narrow planned experiment; the broader failure,
OOB/bad-block and boot-policy limits above remain. No additional device operation is authorized.
