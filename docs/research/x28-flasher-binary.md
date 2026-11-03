# x28-flasher as a single binary (#272)

Owner decision (2026-11-04): ship `x28-flasher` as one downloadable executable per platform (macOS Apple silicon, Linux x86_64,
Windows x86_64 untested), built with PyInstaller from the Python tools in `tools/recovery/` plus the pinned, patched mtkclient
(#270: flashing stays on mtkclient). The Rust tool was dropped.

## Why this touches the guarded tools
Today the guarded scripts assume a developer machine:

| Assumption | Where | In a frozen binary |
|---|---|---|
| a venv at `private/mtkclient-<commit>/venv`; scripts `os.execv` into its Python | `read_by_name.py`, `restore_entry.py`, `slot_entry.py`, `slot_blocks_entry.py` | no venv, no second interpreter |
| `host_identity()` runs `git` in `MTK_HOME/src` and requires the installed `xml_lib.py` to equal pinned source plus `PATCHES` | `restore_entry.py` | no git, no checkout |
| tool hashes are taken over source files on disk | `restore_entry.py` (`tools` digest) | files live inside the bundle |
| the x28-flasher launcher runs the tools with `subprocess` and the venv Python | `x28_flasher.py` | must run them in-process |

So the guards change. That makes this a `risk/brick` change: router-safety-auditor review, and every receipt chain restarts.

## Design
1. **One entry point, in-process dispatch.** `x28-flasher` calls the tools through `runpy` (`x28-flasher read ...` runs `read_by_name`, `flash ...` runs `slot_entry`). No `subprocess`, no `execv`. The venv re-exec blocks are skipped when `sys.frozen` is set; they stay as they are for developers.
2. **Identity without git.** The build (not the user's machine) clones the pinned mtkclient commit, applies `PATCHES`, and stores two things in the bundle: the patched `xml_lib.py` text's SHA-256 and the pinned commit id. In frozen mode `host_identity()` hashes the loaded `xml_lib.py` and compares with that value. The dev path (git + checkout) is unchanged. The `host` field in receipts keeps meaning "exact XML library bytes".
3. **Bundled mtkclient.** Installed from the pinned commit into the build environment, patched, then collected by PyInstaller with its data (`Loader/`, `payloads/`, `Library/Filesystem/bin`). PySide6 (the GUI) is excluded: mtkclient imports it only for the GUI. Expect a binary of a few tens of MB.
4. **libusb.** Bundled per OS (macOS: libusb dylib copied from the build runner; Linux: libusb-1.0.so; Windows: libusb-1.0.dll) and found through pyusb's `find_library`. Linux needs a udev rule for `0e8d:2000/2001`; Windows needs a WinUSB/libusbK driver bound to the MediaTek device (Zadig). Both are documented, not installed by the tool.
5. **The vendor DA is never bundled.** The tool asks for a path (`--loader`, remembered) and checks its SHA-256 against the pinned `DA_HASH`; a wrong file is refused.
6. **Private inputs.** The per-unit full backup and the second copy are created and verified by the tool's own `dump` flow (a later step); until then they are paths the user passes.

## What the frozen identity check proves (auditor review of step 1)
It proves the bundle is self-consistent: the XML library copy equals the hash and pinned commit recorded at build time. It does not
prove source integrity: `identity.json`, the library copy and the pinned commit ship in the same artifact, so the trust root is the
release checksum (and signing, if added). In a PyInstaller build the executing code comes from the compiled archive while
`__file__` points at a data copy, so the later loaded-module hash check cannot see a difference between the two.

Hard gates for the PyInstaller PR, before any frozen `--write`:
- the build asserts that the archive-compiled XML library and every tool source equal the bundled data copies and the recorded hashes;
- the tool-digest code (`here.parent / 'build'`, `slot_session.py`'s `build` import path) is made to resolve from the bundle root, never from a parent of the temp dir (a planted `/tmp/build/*.py` must not be hashed);
- prefer a onedir layout over onefile (user-writable extraction dir);
- `REPO`/`PRIVATE` resolve inside the bundle when frozen, so backup and loader paths are always passed explicitly.

Until those gates and a hand-run read-only test of the frozen binary exist, the frozen binary is for dry-run and read-only use only.

## CI and release
A reusable workflow `x28-flasher.yml` (like `userspace.yml`), called from `release.yml`: a matrix job per OS runs the host tests, builds with PyInstaller, runs a smoke test of the frozen binary (`--selftest`, `ports`, and the identity check against the bundled hash), and uploads `x28-flasher-<os>-<arch>[.exe]` plus `.sha256`. The release job attaches them. Windows ships marked experimental until someone tests it on a real host.

## Steps (separate PRs)
1. This note and the guard changes behind `sys.frozen` / bundled-identity (auditor review; dev behaviour and existing tests unchanged, new tests for the frozen path).
2. The PyInstaller spec and a macOS arm64 build tested by hand on the unit (read-only).
3. The workflow, Linux and Windows builds, checksums, release attachment.
4. `dump` and `verify` subcommands; the guided `flash` run with a frozen binary.

## Not decided
Code signing and notarization (macOS Gatekeeper blocks unsigned downloads until the user allows them), auto-update, and whether the vendor DA can be fetched for the user. None is needed for step 1.
