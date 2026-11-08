# Documentation

Read in this order if you are new (or returning after a long break):

1. [**STATUS.md**](STATUS.md): where the project stands today, what works and what is unproven.
2. [**TESTING.md**](TESTING.md): what has actually been proven, with commands to reproduce it. Start here for evidence.
3. [**ROADMAP.md**](ROADMAP.md): what comes next (recovery slot, `sysupgrade`, stable release).
4. [**PROJECT-PLAN.md**](PROJECT-PLAN.md): goal, strategy, phases, the roadmap to a stable release and the risks.
5. [**BUILD.md**](BUILD.md): how the native image is built (open half in CI, vendor half locally).
6. [**RECOVERY.md**](RECOVERY.md): backup, USB recovery path, UART, flash sessions, safety rules. Read before touching flash.
7. [**BOOT-FLOW.md**](BOOT-FLOW.md): A/B slots, the preloader boot counter, the rootfs signature check.
8. [**NATIVE-CELLULAR.md**](NATIVE-CELLULAR.md): the `x28_mipc` cellular protocol.
9. [**THERMAL.md**](THERMAL.md): heat baseline, the 12 V fan and current readings.
10. [**WORKFLOW.md**](WORKFLOW.md): issues, branches, commits, PRs and automatic releases.
11. [**PACKAGE-FEED.md**](PACKAGE-FEED.md): the signed `opkg` feed for this device line: what installs, what is refused, how to use it.

What changed and when: [../CHANGELOG.md](../CHANGELOG.md).

## Tree

```
docs/
├── README.md                 this index
├── STATUS.md                 current state (older snapshots live in archive/)
├── ROADMAP.md                what comes next, moved out of the README
├── TASKS.md                  task overview by area, with the roadmap items
├── TESTING.md                test log: every test, result, reproduce command, what is not proven
├── PROJECT-PLAN.md           goal, strategy, phase status, roadmap to a stable release, risks, operating rules
├── BUILD.md                  the native image: CI userspace, private staging, first-boot profile, UBI, boot guards
├── HARDWARE.md               CPU, RAM and flash use, the root filesystem tree and the device tree
├── RECOVERY.md               NAND backup, USB preloader/DA access, flash sessions, UART
├── BOOT-FLOW.md              A/B slots, boot counter, selection records and the rootfs signature check
├── NATIVE-CELLULAR.md        the x28_mipc netifd protocol and its hardware validation
├── THERMAL.md                baseline, fan result and the native image reading, how it was measured
├── PACKAGE-FEED.md           the supported X28 opkg feed: URL, key, coverage, limits, how a release is made
├── research/kernel-module-crc.md  TPROXY module CRCs vs the stock kernel, and how they load anyway
├── research/vendor-ipset-packaging.md  ipset packages for the vendor kernel's module subset
├── research/signed-package-feed.md  the signed X28 opkg feed: contents, signing and hosting
├── research/feed-index.txt   the index of the X28 feed that is pinned in feed_release.py (224 packages), for review before signing
├── research/kmod-gap.md      all 976 official kmods sorted by what it takes to run them on 4.19.205 (#394)
├── research/x28-flasher-binary.md  x28-flasher as a single binary: guard changes, identity, CI (#272)
├── research/rust-flasher-design.md  dropped Rust flasher (#270), kept for protocol and DA findings
├── research/reset-wps-buttons.md  reset and WPS button pins, records and boot-time behaviour (no layer wipes flash)
├── PASSWALL2.md              Passwall2 on TPROXY modules for this kernel, unit state, tunnel speed results
├── FIRMWARE-INVENTORY.md     kernel config, modules, vendor packages, runtime deps, fw3 fit, ABI vs 23.05
├── FIRMWARE-EXTRACTION.md    offline extraction of the stock rootfs
├── RECOVERY-BACKUP.md        the verified partition backup and how it is stored
├── DEVICE-AUDIT.md           early read-only audit of the stock firmware
├── DEVELOPMENT.md            repository layout and local checks
├── WORKFLOW.md               trunk-based flow, labels, Conventional Commits, release and changelog rules
├── COMMUNITY-BRIEF.md        the project's public-facing brief
├── research/                 boot-flow, signature, slot-selection and flash-session research and plans
├── firmware/                 the stock kernel's embedded config (identical in both slots) and the device tree
├── assets/                   logo kit (SVG, icons, social preview) and BRAND.md usage guide
├── images/                   board photos (UART footprint)
├── archive/                  superseded plans, readmes and status snapshots
└── (stock-firmware overlay, historical) vendor-command-map.md, luci-on-stock.md, luci-fix-notes.md
```

## More research notes and archive

Older analysis and plans, kept for the evidence behind decisions in the documents above. Each is a point-in-time note; the numbered documents are the current state.

### Research

- [`research/changed-data-restore-plan.md`](research/changed-data-restore-plan.md): Changed-data restore: offline proposal (#62)
- [`research/changed-page-restore-result.md`](research/changed-page-restore-result.md): Changed-page restoration: hardware PASS (#72)
- [`research/content-enforcement.md`](research/content-enforcement.md): Does anything check rootfs content against the signed digest? (#91)
- [`research/first-write-plan.md`](research/first-write-plan.md): First inactive-slot write: review plan, not execution approval (#57)
- [`research/flash-other-units.md`](research/flash-other-units.md): Flashing a unit other than the first one, with no UART and no SSH (#318)
- [`research/gpl-source-request.md`](research/gpl-source-request.md): GPL source request to ZLT/Tozed (#18)
- [`research/live-native-boot-prerequisites.md`](research/live-native-boot-prerequisites.md): Live native-boot prerequisites (#84)
- [`research/lk-authentication-ghidra.md`](research/lk-authentication-ghidra.md): LK authentication paths in Ghidra (#207)
- [`research/lk-boot-auth-preview.md`](research/lk-boot-auth-preview.md): LK boot/recovery authentication: local Ghidra preview (#211)
- [`research/misc-probe-plan.md`](research/misc-probe-plan.md): Plan: learn how the preloader reads `misc` without ever selecting A (check 3)
- [`research/native-image-completeness.md`](research/native-image-completeness.md): Native image completeness (#89)
- [`research/native-image-readiness.md`](research/native-image-readiness.md): Native-image input and boot audit (#74)
- [`research/operator-lock.md`](research/operator-lock.md): The stock firmware's operator (SIM) lock
- [`research/overlay-policy.md`](research/overlay-policy.md): Overlay (`rootfs_data`) policy for the native image (#88)
- [`research/patched-identical-write-result.md`](research/patched-identical-write-result.md): Patched identical-write result (#70)
- [`research/recovery-route-proof.md`](research/recovery-route-proof.md): Proving the way back before the first write (gate 6)
- [`research/rootfs-a-write-plan.md`](research/rootfs-a-write-plan.md): First native image: write, select, recover (plan for #90)
- [`research/rootfs-signed-content.md`](research/rootfs-signed-content.md): What LK authenticates, and the device-test gate (#40)
- [`research/slot-b-reuse.md`](research/slot-b-reuse.md): What the preloader does without slot B, and what B is worth as storage (#302)
- [`research/slot-selection.md`](research/slot-selection.md): Selecting slot A and getting back to B (#92)
- [`research/sysupgrade-design.md`](research/sysupgrade-design.md): Sysupgrade for the A/B layout: design (#154)
- [`research/uart-boot-log.md`](research/uart-boot-log.md): UART boot log: slot choice and signature checks
- [`research/x28-hardware-architecture.md`](research/x28-hardware-architecture.md): X28 hardware architecture
- [`research/x28-mainline-kernel-feasibility.md`](research/x28-mainline-kernel-feasibility.md): X28 mainline kernel feasibility
- [`research/x28-mainline-roadmap.md`](research/x28-mainline-roadmap.md): X28 mainline roadmap
- [`research/x28-modem-driver-analysis.md`](research/x28-modem-driver-analysis.md): X28 modem driver analysis

### Archive (superseded)

- [`archive/2026-10-20-PROJECT-PLAN.md`](archive/2026-10-20-PROJECT-PLAN.md): ZLT X28: custom OpenWrt project plan
- [`archive/2026-10-20-README.md`](archive/2026-10-20-README.md): ZLT X28 OpenWrt
- [`archive/2026-10-21-STATUS.md`](archive/2026-10-21-STATUS.md): Project status — 2026-10-21

## Code map

| Path | What |
|---|---|
| `package/` | OpenWrt packages we wrote: `x28-mipc` (cellular netifd protocol), `luci-proto-x28-mipc` (its LuCI page), `x28-modem` (starts the vendor modem stack), `x28-wifi` (netifd handler for `mt_wifi`), `x28-leds`, `x28-bootok` (A/B boot counter) |
| `tools/build/` | `userspace.sh` (ImageBuilder), `feed_release.py`, `usign/` (signing image), `opkg_real_test.sh`, `kmod_gap.py`, `link_check.py`, `qemu_boot_test.py`, `device_ram_test.sh`, `management_auth_test.py` (image assembly, `stage_native.py`, `first_boot.py`, `ab_guard.py`, `package_ubi.py`, moved to x28-flasher) |
| (moved) | the backup, USB and guarded flash tools live in [mralinp/x28-flasher](https://github.com/mralinp/x28-flasher) (`tools/recovery/`, `tools/x28-flasher/`) |
| `tools/firmware/` | `inventory.py` (kernel config, modules, packages, ELF deps, services), `abi_check.py` |
| `tools/brand/` | `build_logo.py`: regenerates every logo SVG from parameters ([assets/BRAND.md](assets/BRAND.md)) |
| `scripts/` | `release.py` (version and PR-title rules), `changelog.py` (regenerates the release list in CHANGELOG.md), `install.sh` (deploys the stock-firmware overlay), label sync |
| `tests/` | shell tests of the init scripts (`test_modem.sh`, `test_bootok.sh`, `test_wifi.sh`, `test_wps.sh`) and the historical protocol and LuCI tests |
| `router/`, `experiments/` | the stock-firmware overlay and OEM UI experiments (historical; not part of the native image) |
| `.github/workflows/` | `ci.yml`, `userspace.yml`, `release.yml` |

Every analysis tool has a runnable self-check: `python3 tools/firmware/inventory.py selftest`,
`python3 scripts/release.py selftest`, `python3 scripts/changelog.py --check`
(CI runs the self-checks; `changelog.py --check` itself needs `gh` and network access, so only its self-test runs in CI).
