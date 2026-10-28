# Patched identical-write result (#70)

On 2026-10-28 the user approved one original-byte rewrite of inactive `rootfs_sig_a`, manual
preloader entry and a normal B return only after verification. The safety reviewer cleared that
scope. No changed-data write, slot switch, retry, explicit host erase or automatic reboot was authorized.

## Hardware transaction: PASS

| Item | Observed result |
|---|---|
| Tool baseline | merged main `7095625`; guarded `restore_entry.py identical --write` |
| Target | mtd28 `rootfs_sig_a`, `[0x13500000, 0x13600000)`, 1,048,576 bytes |
| Original SHA-256 | `1ebb121adfbac5603dca0e65c3b276a315fda1450bdbd573f3c600b5f399d4b6` |
| Installed XML library SHA-256 | `98af4b9448a5fcacd42f35cc00ab07772b9176246ef47478f2701035fdea6b04` |
| Local preflight | all 51 originals, fixed layout/source/DA and exact pinned-plus-patches host implementation pass |
| Live preflight | slot B, full layout, signature and selection-metadata hashes match the reviewed baseline |
| Unit binding | fresh exact-size DA `proinfo` read matches this unit's private backup hash |
| Before write | target and all five guards acknowledged, exact length and matching SHA-256 |
| Host write attempts | exactly one original-image request; acknowledged `True` |
| After write | target and all five guards acknowledged, exact length and matching SHA-256 in the **same session** |
| Total target/guard reads | 12 matches, 211,812,352 bytes (202 MiB), plus separate unit binding read |
| Final engine/entry state | `ORIGINAL_AND_GUARDS_VERIFIED` / `VERIFIED`; process exit 0 |
| Independent host verification | all twelve saved readbacks rehashed and matched; bound receipt/journal validated |

The guards are `boot_a`, `rootfs_a`, `rootfs_sig_b`, `misc` and `boot_para`; their fixed ranges and
hashes are in the [first-write plan](first-write-plan.md#mandatory-guards). This was an original-byte
write; no certificate or padding byte was deliberately changed.

The UART capture was opened RX-only at 921600, received a valid stock login prompt before arming,
and remained active through entry and the transaction. The first `WRITE-FLASH` text occurs at byte
8,496,511 in this run's private UART file. No `CMD XML(OK) invalid` occurs after it in the captured
transaction. More decisively, all six subsequent reads completed in that same session. This is the
hardware observation previously missing from the [host ACK fix](first-write-plan.md#host-fix-and-remaining-gate).

Setup was **not warning-free**: the host log contains `xread: Wrong length`, unpatched-extension
warnings and an optional extension-builder `TypeError` that was caught and skipped. The pass depends
on explicit acknowledgements, exact lengths, source hashes and all guards, rather than absence of
warnings. The earlier failed same-session run remains separately documented and is not overwritten.

## Return boot

The user performed the approved normal power cycle only after all checks passed. UART records
`ab_suffix: _b` at byte 16,781,224 and `ROOTFS_SIG_VFY Success` at byte 16,808,548 in the same private
capture. After an initial SSH timeout during network startup, read-only SSH confirmed `bootslot=b`,
`ubi.mtd=42`, and both `/dev/mtd28` and `/dev/mtd41` matching the original signature hash above.
The stock-B return boot is therefore verified by both UART and Linux observation.

## Evidence and limits

Private evidence is retained under:

- `private/usb-probe/20261028/patched-host-preparation-b7zscr7d/`: original host library and exact patch/preflight record.
- `private/usb-probe/20261028/patched-identical-write-ndjz_jjd/`: approval, live preflight, host/UART logs and independent result.
- `private/usb-probe/entry-identical-0uaeldpt/`: run-bound receipt, unit read, source snapshot, twelve readbacks and journal.

All 63 recovery tests passed under Python 3.14 before hardware entry. Both original and second
archive were verified, and the second archive is a distinct file on the **same Mac/filesystem**.
The user explicitly approved this disclosed storage limitation; separate physical backup protection
has not been established. No raw capture, image, identity/calibration data or SDK file is published.

This demonstrates the patched completion path and one exact identical rewrite on this unit. It does
not demonstrate restoration of changed data, arbitrary damaged-target recovery, OOB/bad-block handling,
a damaged preloader route, slot-A boot, signature-failure fallback or post-boot content enforcement.
The [changed-data test](changed-data-restore-plan.md) remains a separate operation requiring approval;
its prior-identical gate is bounded to matching implementation/unit identities and a 24-hour window.
