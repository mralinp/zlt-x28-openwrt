# Documentation

Read in this order if you are new (or returning after a long break):

1. [**TESTING.md**](TESTING.md): what has actually been proven, with commands to reproduce it. Start here.
2. [**PROJECT-PLAN.md**](PROJECT-PLAN.md): goal, strategy and phases.
3. [**RECOVERY.md**](RECOVERY.md): backup, USB recovery path, UART, safety rules. Read before touching flash.
4. [**FIRMWARE-INVENTORY.md**](FIRMWARE-INVENTORY.md): what the stock firmware is made of, and what a port needs.
5. [**BUILD.md**](BUILD.md): how the native image is built (open half in CI, vendor half locally).
6. [**WORKFLOW.md**](WORKFLOW.md): issues, branches, commits, PRs and automatic releases.

## Tree

```
docs/
├── README.md                 this index
├── TESTING.md                test log: every test, result, reproduce command, what is not proven
├── PROJECT-PLAN.md           goal, strategy, phases 0–6, risks, operating rules
├── RECOVERY.md               NAND backup, USB preloader/DA access, full USB reads, restore plan, UART
├── FIRMWARE-INVENTORY.md     kernel config, modules, vendor packages, runtime deps, fw3 fit, ABI vs 23.05
├── BUILD.md                  open userspace (ImageBuilder, CI) vs vendor half (local only)
├── WORKFLOW.md               trunk-based flow, labels, Conventional Commits, release rules
├── vendor-command-map.md     the vendor web UI's JSON commands (Stage 1 adapter layer)
├── luci-on-stock.md          how LuCI runs next to the vendor UI on stock firmware
├── luci-fix-notes.md         LuCI dispatcher and session fixes on stock firmware
├── firmware/
│   └── kernel-4.19.205-x28.config   the stock kernel's embedded config (identical in both slots)
├── assets/                   logo kit (SVG, icons, social preview) and BRAND.md usage guide
└── images/                   board photos (UART candidate)
```

## Code map

| Path | What |
|---|---|
| `tools/recovery/` | backup, verify, USB watch, mtkclient setup, security check, USB reads, guarded restore |
| `tools/firmware/` | `inventory.py` (kernel config, modules, packages, ELF deps, services), `abi_check.py` |
| `tools/build/` | `userspace.sh` (ImageBuilder), `link_check.py` (musl link test of the vendor stack) |
| `tools/brand/` | `build_logo.py`: regenerates every logo SVG from parameters ([assets/BRAND.md](assets/BRAND.md)) |
| `scripts/` | `release.py` (version and PR-title rules), `install.sh` (deploy the overlay), label sync |
| `router/` | Stage 1 overlay for the stock firmware: vendor bridge, LuCI pages, `vendorsync`, `templog` |
| `.github/workflows/` | `ci.yml`, `userspace.yml`, `release.yml` |

Every analysis tool has a runnable self-check: `python3 tools/firmware/inventory.py selftest`,
`python3 tools/recovery/common.py`, `python3 scripts/release.py selftest` (all run in CI).
