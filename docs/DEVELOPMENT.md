# Laptop development

The repository is the source of truth for original packages, tests, plans and evidence. Device deployment is a separate explicit step. There is no automatic deploy, flash or service activation on commit.

## Layout

- `package/`: the OpenWrt packages we wrote: `x28-mipc` (cellular netifd protocol) and its LuCI page, `x28-modem`, `x28-wifi`, `x28-leds`, `x28-bootok`.
- `tools/build/`, `tools/recovery/`, `tools/firmware/`: image assembly, guarded flash sessions and firmware analysis, each with host tests.
- `tests/`, `examples/`: shell tests of the init scripts, mocked protocol tests and a disabled configuration.
- `docs/PROJECT-PLAN.md`, `TASKS.md`, `STATUS.md`, `TESTING.md`, `../CHANGELOG.md`: plan, progress, evidence and history.
- `experiments/`: historical OEM UI work and unfinished genuine stock-LuCI preview.
- `router/`: the earlier overlay for the stock firmware; not part of the native image.
- ignored `private/`, `firmware/`, `external/`, `build/`: future private inputs, upstream checkouts and generated artifacts.

## Local checks

```sh
for t in tests/test_modem.sh tests/test_bootok.sh tests/test_wifi.sh; do sh $t; done
python3 -m unittest discover -s tools/build -p 'test_*.py'
for t in tools/recovery/test_*.py; do python3 $t; done
node tests/test_luci.cjs
sh -n package/x28-mipc/files/x28_mipc.sh tests/run-case.sh
```

CI runs the same checks (`.github/workflows/ci.yml`).

`python3 tests/test_native.py --router router` executes mock-only tests with installed OpenWrt helpers through SSH. It stages files in /tmp, mocks modem and ubus operations, and cleans up. It still contacts the active router; read its harness first.

## Firmware inputs

Do not commit raw NAND/UBI images, rootfs exports, calibration, identities, SIM material, private keys or vendor binaries. Use an ignored private location and keep provenance/hashes in a redacted manifest. The existing verified backup remains in the original private workspace; it has not been moved or re-read during this migration. No additional firmware download, source clone or rootfs extraction has been performed here.

The existing community userspace-port reference is gaglians/zlt-x28-openwrt2305 at commit `de4b8bcfad1156c90299d9f0846b42cb1229bfa5`. It requires external SDK/kernel inputs. It is a reference, not our firmware source or proof of device support.

## Migration checks and workflow

Local JS, shell syntax, read-only preview static checks and `git diff --check` passed after migration. The 31 modem lifecycle cases are prior mock-test evidence, not newly repeated hardware tests. A local AST graph was generated with `graphify update .`; it reported an extractor syntax warning in the historical `mtkwifi.lua` copy. That file has not been changed or redeployed. Generated graph output is ignored.

The migration is committed under its own issue (see `docs/WORKFLOW.md`). The historical `mtkwifi.lua` is MediaTek's proprietary controller with unclear redistribution rights, so it is git-ignored and kept only locally; its hash stays in `MIGRATED-SOURCES.sha256` for provenance. The original workspace has been retained as a recovery copy; future development should use this repository.
