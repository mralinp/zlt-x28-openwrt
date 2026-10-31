# Documentation

Read in this order if you are new (or returning after a long break):

1. [**STATUS.md**](STATUS.md): where the project stands today, what works and what is unproven.
2. [**TESTING.md**](TESTING.md): what has actually been proven, with commands to reproduce it. Start here for evidence.
3. [**PROJECT-PLAN.md**](PROJECT-PLAN.md): goal, strategy, phases, the roadmap to a stable release and the risks.
4. [**BUILD.md**](BUILD.md): how the native image is built (open half in CI, vendor half locally).
5. [**RECOVERY.md**](RECOVERY.md): backup, USB recovery path, UART, flash sessions, safety rules. Read before touching flash.
6. [**BOOT-FLOW.md**](BOOT-FLOW.md): A/B slots, the preloader boot counter, the rootfs signature check.
7. [**NATIVE-CELLULAR.md**](NATIVE-CELLULAR.md): the `x28_mipc` cellular protocol.
8. [**THERMAL.md**](THERMAL.md): heat baseline, the 12 V fan and current readings.
9. [**WORKFLOW.md**](WORKFLOW.md): issues, branches, commits, PRs and automatic releases.

What changed and when: [../CHANGELOG.md](../CHANGELOG.md).

## Tree

```
docs/
├── README.md                 this index
├── STATUS.md                 current state (older snapshots live in archive/)
├── TASKS.md                  task overview by area, with the roadmap items
├── TESTING.md                test log: every test, result, reproduce command, what is not proven
├── PROJECT-PLAN.md           goal, strategy, phase status, roadmap to a stable release, risks, operating rules
├── BUILD.md                  the native image: CI userspace, private staging, first-boot profile, UBI, boot guards
├── HARDWARE.md               CPU, RAM and flash use, the root filesystem tree and the device tree
├── RECOVERY.md               NAND backup, USB preloader/DA access, flash sessions, UART
├── BOOT-FLOW.md              A/B slots, boot counter, selection records and the rootfs signature check
├── NATIVE-CELLULAR.md        the x28_mipc netifd protocol and its hardware validation
├── THERMAL.md                baseline, fan result and the native image reading, how it was measured
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
├── images/                   board photos (UART candidate)
├── archive/                  superseded plans, readmes and status snapshots
└── (stock-firmware overlay, historical) vendor-command-map.md, luci-on-stock.md, luci-fix-notes.md
```

## Code map

| Path | What |
|---|---|
| `package/` | OpenWrt packages we wrote: `x28-mipc` (cellular netifd protocol), `luci-proto-x28-mipc` (its LuCI page), `x28-modem` (starts the vendor modem stack), `x28-wifi` (netifd handler for `mt_wifi`), `x28-leds`, `x28-bootok` (A/B boot counter) |
| `tools/build/` | `userspace.sh` (ImageBuilder), `stage_native.py` (private rootfs staging), `first_boot.py` (the management profile and policy), `ab_guard.py` (refuses images whose boot path can write flash), `package_ubi.py` (UBI packaging), `qemu_boot_test.py`, `device_ram_test.sh`, `link_check.py`, `management_auth_test.py` |
| `tools/recovery/` | backup and verify, mtkclient setup, USB reads, and the guarded flash sessions: `slot_entry.py` / `slot_session.py` (`rootfs_a`), `slot_blocks_entry.py` / `slot_blocks.py` (`misc` blocks, `rootfs_sig_a` rehearsal), `restore_entry.py` |
| `tools/firmware/` | `inventory.py` (kernel config, modules, packages, ELF deps, services), `abi_check.py` |
| `tools/brand/` | `build_logo.py`: regenerates every logo SVG from parameters ([assets/BRAND.md](assets/BRAND.md)) |
| `scripts/` | `release.py` (version and PR-title rules), `changelog.py` (regenerates the release list in CHANGELOG.md), `install.sh` (deploys the stock-firmware overlay), label sync |
| `tests/` | shell tests of the init scripts (`test_modem.sh`, `test_bootok.sh`, `test_wifi.sh`) and the historical protocol and LuCI tests |
| `router/`, `experiments/` | the stock-firmware overlay and OEM UI experiments (historical; not part of the native image) |
| `.github/workflows/` | `ci.yml`, `userspace.yml`, `release.yml` |

Every analysis tool has a runnable self-check: `python3 tools/firmware/inventory.py selftest`,
`python3 tools/recovery/common.py`, `python3 scripts/release.py selftest`, `python3 scripts/changelog.py --check`
(CI runs the self-checks; `changelog.py --check` itself needs `gh` and network access, so only its self-test runs in CI).
