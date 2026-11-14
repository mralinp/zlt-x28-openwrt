# Development

## Workflow

1. **Everything is an issue.** No issue, no branch. Labels: one priority (`P0`–`P3`), one `type/*`, one or more `area/*`,
   `risk/*` when relevant, and a phase milestone.
2. Branch from `develop`: `feature|fix|chore|docs|research/<issue>-slug`.
3. Open a PR into `develop` with a Conventional Commit title. Squash-merge.
4. Never push to `develop` or `main` directly.

A PR needs: what and why, `Closes #n`, test evidence from a real unit, a safety note and rollback for `risk/*`, and an explicit
**"not verified"** list. A PR that adds a document also lists it in `docs/README.md` and the root `README.md`.

| Risk label | Means |
|---|---|
| `risk/brick` | flash, bootloader, partitions |
| `risk/lockout` | network, SSH, auth |
| `risk/reboot` | may reboot the unit |

Release rules: [Build and release](Build-and-Release.md#release-model).

## Repository map

| Path | What |
|---|---|
| `package/` | the OpenWrt packages we wrote ([Packages](Packages.md)); `x28-packages.ini` lists what becomes an ipk |
| `tools/build/` | userspace build, feed build and signing, image signing, opkg and QEMU tests |
| `tools/firmware/` | `inventory.py` (kernel config, modules, ELF deps), `abi_check.py`, Ghidra scripts for LK |
| `tools/brand/` | regenerates the logo SVGs |
| `scripts/` | `release.py` (version and PR-title rules), `changelog.py`, label sync |
| `tests/` | shell tests of the init scripts, LuCI view tests, `qemu-sysupgrade/` (simulated NAND) |
| `docs/` | current documents; `docs/research/` point-in-time notes; `docs/archive/` superseded |
| `site/` | the landing page (GitHub Pages); `site/wiki/` is this wiki, rendered by `site/wiki/index.html` |
| `router/`, `experiments/` | the legacy stock-firmware overlay and OEM UI experiments |
| `private/`, `sdk-fg360/`, `vendor-ui/` | git-ignored: backups, the vendor SDK, vendor files |

The flasher, the guarded recovery tools and the image assembly are in
[mralinp/x28-flasher](https://github.com/mralinp/x28-flasher).

## Local checks

```sh
for t in tests/test_*.sh; do sh "$t"; done
python3 -m unittest discover -s tools/build -p 'test_*.py'
node tests/test_luci.cjs
node tests/test_update_luci.cjs
lua package/x28-telephony/files/x28-sms selftest
python3 tools/firmware/inventory.py selftest
python3 scripts/release.py selftest
python3 site/wiki/test_links.py
```

`python3 tests/test_native.py --router x28` runs mock-only tests **on a real router** over SSH. It stages files in `/tmp` and
cleans up, but read the harness first.

## Conventions

- Shell: POSIX / busybox ash. Lua 5.1 (no bit ops, no `//`). JS: vanilla, no build step.
- Keep it small: no abstraction without a second user, no config for constants. Comment only the non-obvious "why".
- Anything non-trivial leaves one runnable check.
- Never commit SSH keys, credentials, `vendor-ui/`, firmware dumps, SDK files, or scratch scripts that embed logins.

## Access to a test unit

| | |
|---|---|
| SSH | `ssh x28` (key auth, port 22; 2222 on old images) |
| LuCI | `https://192.168.70.1/cgi-bin/luci` |
| After Lua/LuCI changes | `rm -rf /tmp/luci-modulecache /tmp/luci-indexcache` |

Rules for touching a unit: [Recovery and safety](Recovery-and-Safety.md#safety-rules-learned-the-hard-way).

## Claude Code agents (`.claude/agents/`)

| Agent | Use |
|---|---|
| `issue-planner` | turn a goal into labeled issues |
| `router-safety-auditor` | review any change that touches the device; required before a `risk/*` PR |
| `lua-luci-reviewer` | review Lua, LuCI and ash code |
| `firmware-researcher` | read-only recon; never writes to the device |

## The vendor SDK

An FG360 SDK for a sibling device arrived officially after vendor support ended. It is used privately to build kernel modules.
Its files are never shared or published; only built `.ko` files go into the feed.

Full documents: [WORKFLOW](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/WORKFLOW.md),
[DEVELOPMENT](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/DEVELOPMENT.md),
[CLAUDE.md](https://github.com/mralinp/zlt-x28-openwrt/blob/main/CLAUDE.md).
