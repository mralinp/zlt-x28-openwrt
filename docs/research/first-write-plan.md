# First inactive-slot write: review plan, not execution approval (#57)

Prepared 2026-10-28 for this X28 and its own verified backup. No device was contacted, written,
or rebooted while preparing this plan. The user has phone internet and accepts replacing the unit;
this does not restore its identity/calibration or establish a working rollback.

**Proposed experiment:** one identical-byte rewrite of `rootfs_sig_a` while slot B remains selected.
It tests the host/DA write transaction and the requested address range. It does **not** prove erase,
restoration of changed data, acceptance of altered rootfs contents, or fallback after a failed boot.

## Target and source

`rootfs_sig_a` is chosen instead of the earlier `lk_a` example to avoid deliberately writing a
bootloader. Both are boot-chain inputs, so this is a reduction in scope, not a guarantee against damage.
The inactive certificate partition is 1 MiB / four `0x40000` erase blocks; no partial erase-block
boundary is requested. Its A/B backups are byte-identical.

| Item | Exact value |
|---|---|
| Target | `mtd28`, `rootfs_sig_a` |
| Absolute main-data offset | `0x13500000` |
| Length | `0x100000` (1,048,576 bytes) |
| End, exclusive | `0x13600000` |
| Source | `private/recovery/20261020-capture-prepared-20261021/images/mtd28-rootfs_sig_a.bin` |
| Source SHA-256 | `1ebb121adfbac5603dca0e65c3b276a315fda1450bdbd573f3c600b5f399d4b6` |
| DA | `private/vendor-da/20261022-mt6890-cpe-recovery-zlt-x28/extracted/DA_BR.bin` |
| DA SHA-256 | `c3d9058aeb56373eaadc5868ce93198fb99a9cbf876a30f876714e9007d66d56` |

These are raw main-data inputs from the verified backup, not a whole-chip image or a sysupgrade file.
Do not substitute another unit's backup or a modified signature image.

## Mandatory guards

The hardened writer checks the full live `/proc/mtd` layout and requires exactly one `bootslot=b`.
In the DA session, it must read the target and **every** guard and match the backup before writing;
a different target is refused as well. The post-write checks cover the target and all guards again.

| Guard | Offset | Length | Expected SHA-256 |
|---|---|---|---|
| `boot_a` (preceding neighbour) | `0x11500000` | `0x2000000` | `c8cc8244078cb6539c72842540250bc7ca40b8fb9b66123a6bd85a529e47b120` |
| `rootfs_a` (following neighbour) | `0x13600000` | `0x4000000` | `5f0c997ddbc0a8380b4785d58048659f26efff5e7d173825972f3ca45646cc36` |
| `rootfs_sig_b` (active-slot twin) | `0x1fb00000` | `0x100000` | `1ebb121adfbac5603dca0e65c3b276a315fda1450bdbd573f3c600b5f399d4b6` |
| `misc` | `0x700000` | `0x100000` | `d8a5b852d2336a8a39a3a09894797de4cd9e14b84425cc12db8d02e4f8cbc780` |
| `boot_para` | `0x8e00000` | `0x200000` | `11fe64ca9cf44765dc451767b862b5ce4c7759fe38b79fd7949297992e054636` |

The target plus guards total 101 MiB per pass, 202 MiB across the planned pre/post checks, plus the
1 MiB write. A guard check detects damage after it occurs; it cannot prevent an incorrect DA write
or prove that every unguarded partition stayed intact.

## Completed read-only rehearsal (2026-10-28)

**PASS: target plus all five guards, 101 MiB / 105,906,176 bytes.** Before USB entry, the
hardened tool's 24 host-only tests passed; the live router reported slot B and a full partition
layout matching the backup. All six local inputs, the DA hash and available host space were checked.
The user manually power-cycled into preloader; the verified DA was uploaded into RAM.
Only flash reads were requested, one per partition:

| Readback | Exact bytes | Result |
|---|---:|---|
| `rootfs_sig_a` | 1,048,576 | MATCH |
| `boot_a` | 33,554,432 | MATCH |
| `rootfs_a` | 67,108,864 | MATCH |
| `rootfs_sig_b` | 1,048,576 | MATCH |
| `misc` | 1,048,576 | MATCH |
| `boot_para` | 2,097,152 | MATCH |

For every read, the DA returned `True`, the file length was exact, and SHA-256 equalled the
corresponding target/guard hash above. An independent host recheck of all six saved files passed.
The host reader exited zero. Setup was not warning-free: the log contains `xread: Wrong length`,
unpatched-extension warnings and an optional extension-builder `TypeError`. Verification depends
on the successful per-read acknowledgement, exact length and matching hash, not absence of warnings.

Private evidence remains in
`private/usb-probe/20261028/read-first-write-guards-r64rdhum/` (`result.json`, `console.log`, six
readbacks). The one-shot host wrapper is scratch, not a newly installed recovery command. An earlier
host logging-wrapper startup error happened before USB connection; the corrected run above has its
own directory. Neither raw readbacks, chip identifiers nor console logs are published.

No flash-write/erase command, slot switch, configuration change or automatic reboot was requested.
This confirms a **point-in-time read baseline**, not write-range safety, erase behavior, or a tested
rollback. The mandatory reads in a future write session must still run again. Return to Linux after
this six-partition session has not yet been observed; the earlier single-partition read session did
return to slot B. Execution approval, the separate backup copy and the rollback gate below remain
unresolved by this read-only pass.

## Gates before the proposed write

1. **Tool version:** [PR #56](https://github.com/mralinp/zlt-x28-openwrt/pull/56) must be merged and its
   hardened code present. Do not run an older writer. The reviewed recovery-tool tree is commit
   `95561c8`; the source below is an additional fingerprint:
   `write_verify.py` SHA-256 `540f4191abe580ce3235d1cec9824c215a153463c1cc60eb88b9398796ee761e`.
2. **Offline tests:** all 24 host-only tests pass, backup and DA identities above match, the source
   stays immutable throughout the session, and a separate physical copy of the backup is confirmed.
   Require at least 512 MiB free on the filesystem holding `private/usb-probe` for the 202 MiB
   readbacks plus logs/headroom. The last full backup-integrity recheck passed; a second storage copy
   has not been established here.
3. **Recovery review:** acknowledge that the current writer only accepts an already matching target.
   It cannot repair a changed target without a separate reviewed operation. No tested damaged-target
   rollback or BROM route is established. This remains a hardware execution gate, not a solved item.
4. **UART:** have the already proven 1.8 V-to-3.3 V shifted RX capture running at 921600 8N1 with
   common GND and a private host log. Record the exact port, capture command and log path in the run
   record. `/dev/cu.usbserial-0001` was listed on the host during preparation, but was not opened or
   established as the correct connected capture adapter. Do not use `stty; cat`, drive an unshifted
   TX pin, enter passwords, or assume a console login provides a NAND restore path.
5. **Stable session:** no stock upgrade/FOTA or slot-switch operation may be pending or running.
   Confirm the selected B record and absence of pending update state in a separately reviewed
   read-only preflight. Equal guard hashes alone do not explain the vendor's future reset policy.
6. **Explicit approval:** the user must approve this exact target, one host write request, the USB
   recovery entry power cycle, and a return-to-stock power cycle only after verification passes.
   Approval to prepare this document, merge a PR, or run a dry-run is not that approval.

The repository requires a tested way back before boot-chain writes ([CLAUDE.md](../../CLAUDE.md)).
This plan does not silently waive that requirement. Until gate 3 is resolved or the user explicitly
changes the test constraint after reviewing the risk, this document is **not ready to execute**.

## Host preflight commands (no flash)

From the repository root, after #56 merges:

```sh
git diff --exit-code 95561c8 -- tools/recovery/
python3 tools/recovery/test_write_verify.py
shasum -a 256 tools/recovery/write_verify.py \
  private/recovery/20261020-capture-prepared-20261021/images/mtd28-rootfs_sig_a.bin \
  private/vendor-da/20261022-mt6890-cpe-recovery-zlt-x28/extracted/DA_BR.bin
```

Stop on any difference or failed test; do not automatically accept a newer tool or source.
A later read-only live preflight can run:

```sh
python3 tools/recovery/write_verify.py rootfs_sig_a
```

Expected: target `mtd28`, offset `0x13500000`, size `0x100000`, `bootslot=b`, and the five guards
above, ending `dry run: no USB command or write issued; identical rewrite requires --write.`
This dry-run uses key-only SSH but does not enter USB recovery, write flash, or reboot.
Neither live preflight command nor a serial port was opened during this plan's preparation.

## Reviewed command for the later approval, not run

Only after every gate is satisfied and the operation is explicitly approved:

```sh
(
set -eu
set -o pipefail
umask 077
mkdir -p private/usb-probe
first_write_logdir="$(mktemp -d "$PWD/private/usb-probe/first-write-rootfs-sig-a-XXXXXX")"
: > "$first_write_logdir/host.log"
python3 tools/recovery/write_verify.py rootfs_sig_a \
  --backup "$PWD/private/recovery/20261020-capture-prepared-20261021" \
  --loader "$PWD/private/vendor-da/20261022-mt6890-cpe-recovery-zlt-x28/extracted/DA_BR.bin" \
  --write 2>&1 | tee "$first_write_logdir/host.log"
)
```

Keep UART capture running. At the tool's explicit prompt, the operator performs the approved
power cycle for preloader/DA entry. The router stays in recovery until another power cycle;
closing the host connection does not boot Linux. Record the new tool-created
`private/usb-probe/<date>/restore-rootfs_sig_a-*` directory alongside the host/UART logs.
Do not confuse an older run's readbacks with this run.

Log setup must succeed before the writer starts; the subshell exits on setup errors, and the transcript
is pre-created before the pipeline. These controls do not eliminate a later full disk or disconnected
log stream. The writer must obtain successful DA acknowledgements and exact-size, matching SHA-256 readbacks.
Its host limit is one `WRITE-FLASH` request; internal DA operations remain unverified. Expected final
status: `IDENTICAL REWRITE VERIFIED` and process exit 0. A successful acknowledgement alone, a partial
file, or the matching target without all matching guards is insufficient.

## Result and stop branches

| Observation | Action |
|---|---|
| Any pre-write target/guard/layout/slot/source discrepancy | No write. Preserve logs; reassess the baseline. If already in DA mode, review and explicitly approve how to leave it. |
| Failed write/read, short/oversized data, changed target or guard, exception, or missing evidence | Stop. No second host write, no separate erase, no slot switch, no normal reboot recommendation. Retain power/recovery state if safely possible and review logs first. |
| Exact target and all guards match, write acknowledgement succeeds, exit 0 | End the test. Only the approved normal power cycle may follow, with UART capture; do not boot slot A. |
| Stock B boot does not complete or UART shows an unexpected slot/path | Do not improvise flash/slot commands. Preserve the trace and return to review of the recovery route. |

After a fully verified write and the approved normal boot, read-only confirmation is:

```sh
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes router \
  'cat /proc/cmdline; sha256sum /dev/mtd28 /dev/mtd41'
```

Require `bootslot=b` and both signature-partition hashes equal the source hash above. Capture the
normal B boot in UART too; SSH alone does not establish where an earlier boot stage ran.
No active partition, preloader, slot metadata, network setting, or vendor upgrade script is deliberately
written by this plan. Unexpected side effects remain a reason to stop, not a reason to retry.

## Rollback limitation and next experiment

There is **no demonstrated rollback command for a damaged target**. The current checker deliberately
rejects such a target before writing. Removing that check, issuing `mtd write`, invoking a vendor
upgrade helper, or changing slots is not an approved fallback. A failed experiment needs a new,
reviewed recovery operation using preserved originals and its actual readbacks. Keep another copy
of the complete identity/calibration backup outside this machine before accepting that risk.

A pass records only: one acknowledged identical-byte write, exact target/guard readback, and a normal
stock-B boot if observed. The separate changed-data erase/restore experiment must then be designed
and approved; an altered-rootfs boot or a bad-signature boot remains beyond this first test.

## Observed execution (2026-10-28, #57 / #60)

**Partial protocol failure, then verified recovery reads and normal B boot.** The single approved
identical rewrite of `rootfs_sig_a` received `WRITE-FLASH` success. All six pre-write reads matched.
The tool then failed its first same-session post-read (`xread: Wrong length`); it exited 1 and
produced no post-read files. This was not the planned clean `IDENTICAL REWRITE VERIFIED` result.
No write retry was issued.

The private UART capture shows the requested `NAND-WHOLE` range `0x13500000`, length `0x100000`.
The DA reports erasing four blocks at `0x13500000`, `0x13540000`, `0x13580000`, `0x135c0000`
(NAND commands `0x60`/`0xd0`), then programming the first page and skipping the 255 empty pages.
After `Download_data end.`, it sends END/OK and START, but receives a bare host `OK` as the
next XML command: `CMD XML(OK) invalid.`, `ERR!UNSUPPORTED`, then
`REVEIVING END CMD Result ERROR. halt.` (near UART byte 8,262,190).
This establishes erase/program activity on this run, rather than only a host API acknowledgement.

After reviewing that failure and obtaining separate approval for a fresh read-only DA session,
the target and all five guards were read again: **six exact-length matches, 105,906,176 bytes**.
The approved return boot then completed on **slot B**, with UART `ROOTFS_SIG_VFY Success`.
Read-only SSH confirmed `bootslot=b`, `ubi.mtd=42`, and both `/dev/mtd28` and `/dev/mtd41`
SHA-256 `1ebb121adfbac5603dca0e65c3b276a315fda1450bdbd573f3c600b5f399d4b6`.

Evidence remains private under `private/usb-probe/20261028/`:
`first-write-rootfs_sig_a-h6i2qujs/` (host/UART/outcome),
`restore-rootfs_sig_a-zr_t1yxa/` (pre-reads), and
`read-verify-after-first-write-xrthz8fh/` (fresh post-reads and result).
All 51 original raw backups were verified before the write; a second verified archive was made
on the **same Mac**, not on separate physical storage.

### Host fix and remaining gate

The pinned mtkclient `upload(raw=True)` sends an extra ACK before reading END.
Its normal END and START handlers already acknowledge both commands. The installer now removes
only that raw-only ACK; the normal completion acknowledgements remain. An offline scripted peer
reproduces the original failure and checks that patched raw and normal uploads leave the peer ready
for the next command. The same check also passed against the actual pinned installed `upload`
method without importing USB code. At that stage the fix had not been exercised on hardware;
the subsequent [#70 result](patched-identical-write-result.md) records a passing identical-mode
transaction with all same-session reads and normal B return.

This proves an identical-byte erase/program followed by matching fresh-session reads and a normal
stock-B boot. It does **not** prove restoring changed data, booting slot A, bad-block handling,
recovery after damage to the preloader, or rootfs enforcement. Before any changed-data test,
review a separately scoped restore operation (including a way to restore a deliberately mismatching
target, which the current checker rejects), preserve the original, define exact guard reads and stop
conditions, and obtain approval for that specific device operation. No further flash write is authorized
by the host fix.
