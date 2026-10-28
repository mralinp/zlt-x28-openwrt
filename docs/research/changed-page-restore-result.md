# Changed-page restoration: hardware PASS (#72)

On 2026-10-29 the user approved the bounded changed-data operation after clarification that this
was the last planned recovery test, while custom-image checks remain separate. Main/tool baseline
was `4961bdd`. The independent safety reviewer cleared the exact two-write scope. The guarded
entry accepted the matching, recent [#70 identical-mode evidence](patched-identical-write-result.md).
No SDK firmware, slot switch, retry, generic damaged-target override or host reboot command was used.

## Exact operation and observed result

Target: inactive `rootfs_sig_a`, mtd28, main-data `[0x13500000, 0x13600000)`, length `0x100000`.
Both requests wrote the full 1 MiB partition. The candidate changed **only 4,096 bytes** at relative
`[0x40000, 0x41000)` / absolute `[0x13540000, 0x13541000)` from `ff` to `aa 55` repeated 2,048 times.
Both certificate structures and every other byte were preserved. This page was erased in the backup;
it was not assumed to be a documented vendor scratch area.

| Phase | Target SHA-256 | Guard result |
|---|---|---|
| Before either write | `1ebb121adfbac5603dca0e65c3b276a315fda1450bdbd573f3c600b5f399d4b6` | all five match originals |
| After candidate write | `20f35f4368ca7bc1447b459d92e1aacb759245b983cd102f28f524e025972e90` | all five match originals |
| After original restore | `1ebb121adfbac5603dca0e65c3b276a315fda1450bdbd573f3c600b5f399d4b6` | all five match originals |

The five guards are `boot_a`, `rootfs_a`, `rootfs_sig_b`, `misc` and `boot_para`, at the fixed
[ranges and hashes](first-write-plan.md#mandatory-guards). All **18 reads** returned acknowledged
success, exact lengths and expected hashes: **317,718,528 bytes / 303 MiB**, plus the separate fresh
unit-binding `proinfo` read. The journal records exactly two acknowledged write attempts, candidate
then original. Every post-candidate check completed before the original write was attempted.
The process exited **0**, entry receipt is `VERIFIED`, and the final journal state is
`ORIGINAL_AND_GUARDS_VERIFIED`.

An independent host recheck rehashed all 18 saved files and validated the receipt/journal identity.
Full byte comparisons establish:

- the staged readback equals the deterministic candidate, changing exactly the intended 4,096 bytes;
- before and final target readbacks are byte-identical to the verified original image;
- both saved source snapshots equal their respective readbacks;
- the programmed pattern page returned completely to `ff`, and all guards matched in all three passes.

Thus this run demonstrates **restoration of deliberately changed data in this page on this unit**.
It establishes the visible programmed-to-erased result through the tested DA path, without claiming
that a readback proves every detail of its physical erase algorithm, OOB handling or remapping.

## Preconditions, protocol and return boot

Fresh key-only SSH confirmed B, `ubi.mtd=42`, the full fixed layout, original signature partitions
and selection-metadata hashes. Bounded update checks found no active write/upgrade helper; the FOTA
startup log showed its switch `0` and its threads sleeping/selecting. This is point-in-time evidence,
not a guarantee against future update activity. Local preflight revalidated all 51 raw originals,
source/DA/installed-host identities and the prior identical-mode receipt. The installed XML library
SHA-256 remained `98af4b9448a5fcacd42f35cc00ab07772b9176246ef47478f2701035fdea6b04`.
All 63 host recovery tests had passed with the same implementation.

RX-only UART capture at 921600 received a valid login prompt before arming, then recorded recovery
and normal return. The first command-text occurrences for the staged and original writes are at
UART file bytes 8,470,557 and 16,704,720. The journal, rather than repeated log strings, establishes
the two host write attempts. No `CMD XML(OK) invalid` was observed after the first write in this capture.

Setup still emitted `xread: Wrong length`, unpatched-extension warnings and a caught optional
extension-builder `TypeError`. This is not a warning-free session claim. Explicit acknowledgements,
exact complete readbacks, hashes and full comparisons establish the result.

The capture's final DA read command appears at byte 24,682,480, followed by the return boot selecting
`ab_suffix: _b` at byte 24,992,784 and `ROOTFS_SIG_VFY Success` at byte 25,020,107. Read-only SSH then
confirmed `bootslot=b`, `ubi.mtd=42`, and both `/dev/mtd28` and `/dev/mtd41` matching the original
signature hash above. The final stock-B return is verified. No boot with the candidate was observed.
The host RX logger was stopped cleanly after this confirmation; no UART login/password was entered.

## Evidence and remaining boundaries

Private evidence remains in:

- `private/usb-probe/changed-data-preparation-4u2rzmdl/`: exact candidate and prerequisite preparation.
- `private/usb-probe/changed-page-test-tq4nnbk9/`: approval, sanitized live preflight, host/UART logs,
  independent result, return SSH output and capture script.
- `private/usb-probe/entry-test-llfcn5mq/`: bound receipt, unit read, both source snapshots,
  18 readbacks and durable journal.

The second complete archive was verified and is a distinct file on the **same Mac/filesystem**.
That limitation was disclosed and approved for this scope; separate physical backup protection is
still absent. Raw logs, firmware, device identity/calibration and SDK content remain uncommitted.

This completes the planned bounded recovery test. It does **not** establish universal rollback,
restoration after arbitrary corruption/power loss, restore-only re-entry after a failed run,
bad-block/OOB correctness, damaged-preloader entry, slot-A/custom-image bootability or rootfs signature
and content enforcement. The next work is offline image and signature/boot compatibility review;
this pass is not approval to flash or boot a custom image. Any newly discovered failure condition
requires review rather than a promise that no further testing can ever be needed.
