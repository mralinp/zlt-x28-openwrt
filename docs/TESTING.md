# Test log

Everything this project has tested, what it proved, how to run it again, and what it did **not** prove.
Written for whoever picks this up later with no memory of the sessions: start here before trusting a claim
anywhere else in the repo.

Conventions:
- **Device**: one ZLT X28, OEM firmware 1.5.13, OpenWrt 19.07-derived, kernel 4.19.205, active slot **B**.
- **Host**: Apple Silicon Mac (macOS), Docker Desktop (arm64 Linux, plus x86_64 emulation).
- Private outputs (dumps, probe logs, chip IDs, vendor files) live in git-ignored `private/` and are never
  committed. Paths below under `private/` are on the maintainer's machine.
- Commands run from the repository root unless noted.

## Summary

| # | Test | Date | Result | Doc |
|---|---|---|---|---|
| 1 | Full NAND backup over SSH, verified | 2026-10-20/21 | ✅ 51 partitions, 1,072,168,960 bytes, all SHA-256 match | [RECOVERY](RECOVERY.md) |
| 2 | USB recovery port at power-on | 2026-10-21 | ✅ preloader `0e8d:2000`, **USB-A-to-C only** | [RECOVERY](RECOVERY.md) |
| 3 | Preloader boot-security config | 2026-10-21 | ✅ SBC, SLA, DAA all **off** | [RECOVERY](RECOVERY.md) |
| 4 | Download agents for flash access | 2026-10-21/22 | ✅ only mtkclient `7cb40e7` + Quectel `DA_BR.bin` reads | [RECOVERY](RECOVERY.md) |
| 5 | USB read of `lk_b` vs backup | 2026-10-22 | ✅ byte-identical | [RECOVERY](RECOVERY.md) |
| 6 | USB read of all 51 partitions, twice | 2026-10-22 | ✅ 44 match, 7 differ (all runtime-written) | [RECOVERY](RECOVERY.md) |
| 7 | Restore one inactive-slot partition | — | ⏸️ not run (safety audit: NO-GO until UART or a spare unit) | [RECOVERY](RECOVERY.md) |
| 8 | Kernel config and module inventory | 2026-10-23 | ✅ config recovered; no `nf_tables`, no DSA | [FIRMWARE-INVENTORY](FIRMWARE-INVENTORY.md) |
| 9 | Runtime dependency map | 2026-10-23 | ✅ modem 4 vendor pkgs, cellular ~11, Wi-Fi tied to Tozed apps | [FIRMWARE-INVENTORY](FIRMWARE-INVENTORY.md) |
| 10 | fw3 fit on the stock kernel | 2026-10-23 | ✅ fits; gaps: `ip6table_raw`, `xt_hashlimit`, flow offload | [FIRMWARE-INVENTORY](FIRMWARE-INVENTORY.md) |
| 11 | ABI check vs OpenWrt 23.05 (static) | 2026-10-23 | ✅ works with 4 compat libs from 19.07 | [FIRMWARE-INVENTORY](FIRMWARE-INVENTORY.md) |
| 12 | Userspace build (CI and local) | 2026-10-23 | ✅ 177 packages, 4.7 MB, no firewall4/nftables | [BUILD](BUILD.md) |
| 13 | Automatic release | 2026-10-23 | ✅ `v0.1.0` pre-release with verified assets | [WORKFLOW](WORKFLOW.md) |
| 14 | musl link test of the vendor stack on `v0.1.0` | 2026-10-23 | ✅ 10/10 binaries resolve | this page |
| 15 | UART console | — | 🚧 candidate pads found, unconfirmed | [RECOVERY](RECOVERY.md#uart-debug-console-2-in-progress) |

Nothing has been **written** to the device's flash by this project, and no native image has booted yet.

## Lab setup

- **Internet**: the X28 is normally the home connection. For any test that takes it offline (all USB work
  holds it in download mode until a power cycle), route the LAN through another router first. Used here: a
  Linksys MX5300 on OpenWrt 25.12 with the phone hotspot as `wwan` (metric 10), the X28 on `wan` (metric 20)
  as fallback, and a `wwan6` interface for IPv6. The Mac still reaches the X28 at `192.168.70.1:2222` through
  the Linksys WAN link.
- **USB**: a **USB-A-to-USB-C** cable from a USB-A port to the X28. USB-C-to-USB-C does not work (test 2).
- **Power-cycle procedure** for every USB test: start the script first (it waits), unplug the X28's power,
  wait ~5 s, plug it back in. mtkclient refuses a device that is already connected when it starts.
- **Analysis volume**: Docker volume `x28-rootfs-b-analysis-20261021` holds the extracted stock rootfs (slot B)
  on a case-sensitive filesystem; image `x28-firmware-tools:local` has Python 3.12, ubi_reader and squashfs-tools.

## 1. Full NAND backup over SSH

- **Setup**: root SSH to the running X28 (`ssh router`).
- **Run**: `python3 tools/recovery/dump_partitions.py` (streams `nanddump --bb=padbad -q /dev/mtdN` per
  partition into gzip files with SHA-256 and ECC notices), then
  `python3 tools/recovery/verify_backup.py private/backups/<date>`.
- **Result**: 2026-10-20 capture, 51 partitions, 1,072,168,960 bytes. Verification on 2026-10-21 and again with
  the rewritten `verify_backup.py` on 2026-10-22 reproduced the original `SHA256SUMS` exactly.
- **Not proven**: OOB/spare data (not captured), YAFFS tag layout, consistency of partitions that were mounted
  and writable during the capture.

## 2. USB recovery port at power-on

- **Run**: `python3 tools/recovery/usb_watch.py`, then power-cycle the X28.
- **Result**:
  - USB-C-to-C, two attempts, and a known data cable: **no device**. The Mac logged no USB-C attach and no
    accessory event (`/usr/bin/log show --info --debug … Port-USB-C`), so macOS accessory security was not
    the cause; the likely cause is a missing CC pull-down on the X28's port (inferred, not measured).
  - USB-A-to-C: `0e8d:2000 MT65xx Preloader` for **~1.15 s** about 13 s into the watch, then
    `2c7c:7003 RG500L-EU` (Quectel Linux gadget) for ~1.7 s at kernel ~24.5–26.5 s.
- **Also learned**: firmware type `usr` skips `adbd`; `switch_otg_daemon` flips USB roles; the preloader skips
  USB entirely when it sees no VBUS (`PMIC not dectect usb cable!`).

## 3. Preloader boot-security config

- **Run**: `python3 tools/recovery/target_config.py` (mtkclient `gettargetconfig --skipwdt`; reads only).
- **Result**: MT6880/MT6890, hw code `0x992`, subcode `0x8a00`, hw ver `0xca01`, sw ver `0x1`. Target config
  `0x0`: **SBC, SLA, DAA, root cert, memory read/write auth all off.** ME_ID was read and kept private.

## 4. Download agents (DA) for flash access

| mtkclient | DA | Outcome |
|---|---|---|
| v2.1.4.1 | bundled `MTK_DA_V6.bin` (built for the **Fibocom FM350**, MT6880) | loads; `READ-FLASH`, `READ-PARTITION` (first command of a fresh session), `READ-PARTITION-TABLE` all `ERR!UNSUPPORTED` |
| v2.1.4.1 | Quectel `DA_BR.bin` (`MTK_DA_v6_2023-06-28`, built by Quectel for T750) | loads; NAND seen correctly (page `0x1000`, spare `0x40`, block `0x40000`, total `0x3ff00000`); `READ-FLASH` still unsupported |
| **`7cb40e7`** (upstream, 2026-10-12) | Quectel `DA_BR.bin` | **`READ-FLASH` works** |

- **Why**: v2.1.4.1 mistakes the DA's unsolicited log packets for replies and sends an older
  `SET-RUNTIME-PARAMETER`; upstream fixed both.
- **Local patches needed** (applied by `tools/recovery/setup_mtkclient.py`): remove `fusepy`/`mfusepy`
  (no libfuse on macOS); `check_sla()` on an empty reply; empty NAND `page_parity_size`; skip the optional DA
  extensions that crash on this DA.
- **DA source**: the community package `spft-x28-nand-unlocked.zip` from
  [mt6890-cpe-recovery](https://github.com/mt6890-cpe-recovery/mt6890-cpe-recovery) (sha256 `67a4fbc3…`).
  Its other images match this unit's firmware byte for byte; its `DA_BR.bin` does **not** match the package's
  own `MD5SUMS` (provenance gap, recorded). Never flash that package's rootfs (known root password, telnet).
- **Reproduce**: `/opt/homebrew/bin/python3.14 tools/recovery/setup_mtkclient.py`; put the DA at
  `private/vendor-da/20261022-mt6890-cpe-recovery-zlt-x28/extracted/DA_BR.bin`.

## 5. USB read of `lk_b`

- **Run**: `python3 tools/recovery/read_verify.py lk_b` (one `READ-FLASH NAND-WHOLE 0x1d800000 0x200000`).
- **Result**: `0ad94f065ebcfeefd157640d179b1b52779829a85179d07d38dd818b79007156` = backup. Also proves the
  partition offsets computed from `/proc/mtd` (back to back from 0).

## 6. USB read of all 51 partitions

- **Run**: `python3 tools/recovery/read_all.py` (one session, one `READ-FLASH` per partition; `--from NAME`
  resumes). A single 1 GiB `READ-FLASH` died with `USBError(32, 'Pipe error')` after 236 MiB, hence per
  partition.
- **Result** (two runs, 2026-10-22, ~0.67 MB/s, ~25 min): **44 MATCH**, **7 DIFF**. The DIFFs are `nvdata`,
  `protect1/2` (modem NV and calibration), `rootfs_b` (active UBI with the writable overlay), `user_config`,
  `productinfo` and `user_data`. Every static firmware partition matches, including both preloaders, every
  slot-A partition and slot B except `rootfs_b`. `misc` (A/B boot control) and `boot_para` were unchanged
  across reboots.
- **Lesson**: restore only static partitions; NV partitions only as a last resort (they change between boots).

## 7. Restore an inactive-slot partition (not run)

- **Script ready**: `python3 tools/recovery/write_verify.py lk_a` (dry run by default). It accepts only `*_a`
  partitions while the router reports `bootslot=b`, reads guard partitions (neighbours, slot-B twin, `misc`,
  `boot_para`) before and after, and stops on any change.
- **Safety audit** (`router-safety-auditor`, 2026-10-22): **NO-GO on the only unit**. Writing back
  identical bytes cannot prove the DA erases before programming, and there is no recovery yet if slot A
  breaks and the unit ever falls back to it.
- **Plan**: on a spare unit, write different content and restore it; then, with UART attached, the
  identical-bytes test on this unit.

## 8. Kernel config and module inventory

- **Run**: `python3 tools/firmware/inventory.py kconfig <backup>/images/mtd40-boot_b.bin out.config`; the
  rootfs part in Docker (see [FIRMWARE-INVENTORY](FIRMWARE-INVENTORY.md)).
- **Result**: embedded config (`IKCONFIG`) identical in both slots →
  [`firmware/kernel-4.19.205-x28.config`](firmware/kernel-4.19.205-x28.config). `MODVERSIONS=y`, no module
  signing, **no `NF_TABLES`**, no DSA. 146 modules, 91 iptables/ebtables, `mt_wifi` the only `Proprietary`
  one. 104 of 346 packages (78.5 MiB) are vendor code.

## 9–11. Runtime dependencies, fw3 fit, ABI check

All in [FIRMWARE-INVENTORY](FIRMWARE-INVENTORY.md), each with its reproduce command. In short:
- Modem bring-up runs at `S00` and needs 4 vendor packages; cellular data about 11; the stock Wi-Fi script
  calls Tozed's `lan_mgr`/`devinfo`.
- fw3 + iptables-legacy fits the stock modules.
- Static ABI: `libc` (musl), `libgcc_s`, `libstdc++`, `libasound` and `libuci` from 23.05 work; `libubox.so`,
  `libubus.so.20210603`, `libjson-c.so.2` and `libnl-tiny.so` must ship from 19.07 (~168 KB).
- A bug found and fixed on the way: OpenWrt's `sstrip` removes section headers, so symbols must be read
  through the dynamic segment (`inventory.elf_symbols`).

## 12. Userspace build

- **Run**: CI on any PR touching `tools/build/` (`.github/workflows/userspace.yml`), or locally per
  [BUILD](BUILD.md).
- **Result**: official 23.05.5 `armsr/armv8` ImageBuilder (pinned sha256 `af89b96d…`); **177 packages**, 4.7 MB
  rootfs. Contains fw3 and iptables 1.8.8 legacy, `netifd`, `dnsmasq`, `dropbear`, musl 1.2.4 and LuCI from
  parts; **no firewall4/nftables**. CI took 1 min 44 s; local under x86_64 emulation 5.5 min.
- **Local gotchas**: `python3-distutils` is required; ImageBuilder refuses case-insensitive filesystems, so keep
  `WORK` inside the container on a Mac.

## 13. Automatic release

- **How**: every merge to `main` runs `.github/workflows/release.yml` ([WORKFLOW](WORKFLOW.md)).
- **Result**: `v0.1.0` created 2026-10-23 as a **pre-release**, about 2 min after the merge. Assets
  (`x28-userspace-v0.1.0-openwrt-23.05.5-armsr-armv8-rootfs.tar.gz`, manifest, `SHA256SUMS`) were downloaded
  and verified against `SHA256SUMS`.

## 14. musl link test of the vendor stack on `v0.1.0`

- **Question**: do the vendor modem, cellular and switch binaries actually load on the released userspace?
- **Run** (arm64 Docker on the Mac, no network; the scratch tree with vendor files stays in the container):
  ```bash
  gh release download v0.1.0 --repo mralinp/zlt-x28-openwrt -D private/build/release-v0.1.0
  docker run --rm --network none -v x28-rootfs-b-analysis-20261021:/r:ro \
    -v "$PWD/tools:/tools:ro" -v "$PWD/private:/p:ro" x28-firmware-tools:local \
    python3 /tools/build/link_check.py --old-rootfs /r/rootfs \
      --userspace /p/build/release-v0.1.0/x28-userspace-v0.1.0-openwrt-23.05.5-armsr-armv8-rootfs.tar.gz \
      --ipk /p/third-party/openwrt-23.05.5/dl/*.ipk
  ```
  `--ipk` adds 23.05.5 `libstdcpp6`, `alsa-lib` and `libnl-tiny1` (SHA-256 checked when downloaded).
- **Result**: **10/10 resolve** with musl's own loader (`ld-musl-aarch64.so.1 --list`, which performs all
  relocations): `nvram_daemon`, `ccci_fsd`, `ccci_mdinit`, `mtk_netagent`, `mipc_wan_cli`, `ql_netd`,
  `ql_ril_service`, `mipc_submonitor`, `hwnat`, `switch`. The only libraries taken from 19.07 were the 9
  vendor libraries and exactly the 4 predicted compatibility libraries.
- **Watch item**: 6 of the 10 load **two libubox copies** (19.07 `libubox.so` directly, 23.05
  `libubox.so.20230523` via 23.05's `libuci`). musl binds globally in load order, so `libuci`'s four libubox
  calls (`blob_nest_end`, `blobmsg_add_field`, `blobmsg_open_nested`, `blobmsg_parse`) go to the 19.07 copy.
  All four exist there and belong to the long-stable blobmsg API, but exercise a UCI path on the device.
- **Not proven**: running the programs (they need the modem's `/dev/ccci*` devices), `dlopen` and Lua
  `require` dependencies, symbol versions (`GLIBCXX_*`).

## 15. UART

See [RECOVERY: UART](RECOVERY.md#uart-debug-console-2-in-progress). Candidate 3-hole footprint on the
back side (none of the holes is ground); logic level unknown (1.8 V reported for a similar board). Waiting on a
level shifter. **Do not wire a 3.3 V adapter's TX directly.**
