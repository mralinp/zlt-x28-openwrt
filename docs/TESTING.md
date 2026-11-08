# Test log

Everything this project has tested, what it proved, how to run it again, and what it did **not** prove.
Written for whoever picks this up later with no memory of the sessions: start here before trusting a claim
anywhere else in the repo.

Conventions:
- **Device**: one ZLT X28, kernel 4.19.205. Tests 1–22 ran on the stock firmware (OEM 1.5.13, OpenWrt 19.07-derived, active slot **B**); tests 23–31 ran on the native image on slot **A**.
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
| 7 | Restore one inactive-slot partition | 2026-10-29 | ✅ exact changed-padding page restored; arbitrary recovery remains unproven | [Changed-page restore result](research/changed-page-restore-result.md) |
| 8 | Kernel config and module inventory | 2026-10-23 | ✅ config recovered; no `nf_tables`, no DSA | [FIRMWARE-INVENTORY](FIRMWARE-INVENTORY.md) |
| 9 | Runtime dependency map | 2026-10-23 | ✅ modem 4 vendor pkgs, cellular ~11, Wi-Fi tied to Tozed apps | [FIRMWARE-INVENTORY](FIRMWARE-INVENTORY.md) |
| 10 | fw3 fit on the stock kernel | 2026-10-23 | ✅ fits; gaps: `ip6table_raw`, `xt_hashlimit`, flow offload | [FIRMWARE-INVENTORY](FIRMWARE-INVENTORY.md) |
| 11 | ABI check vs OpenWrt 23.05 (static) | 2026-10-23 | ✅ works with 4 compat libs from 19.07 | [FIRMWARE-INVENTORY](FIRMWARE-INVENTORY.md) |
| 12 | Userspace build (CI and local) | 2026-10-23 | ✅ 177 packages, 4.7 MB, no firewall4/nftables | [BUILD](BUILD.md) |
| 13 | Automatic release | 2026-10-23 | ✅ `v0.1.0` pre-release with verified assets | [WORKFLOW](WORKFLOW.md) |
| 14 | musl link test of the vendor stack on `v0.1.0` | 2026-10-23 | ✅ 10/10 binaries resolve | this page |
| 15 | UART console | 2026-10-28 | ✅ shifted RX capture at 921600; boot and recovery logs recorded | [RECOVERY](RECOVERY.md#uart-debug-console-2-read-side-confirmed) |
| 16 | 23.05 userspace boots and works (QEMU) | 2026-10-23 | ✅ 12/12: procd, netifd, fw3 ruleset, ubus, LuCI | this page |
| 17 | 23.05 userspace runs on the X28 (RAM chroot, stock 4.19) | 2026-10-23 | ✅ 10/10: musl, uci, iptables-legacy, fw3 print, ubus/rpcd, LuCI; router state unchanged | this page |
| 18 | Rootfs signed metadata and active content match (#40) | 2026-10-28 | ✅ offline RSA-PSS checks and read-only live SquashFS hash agree; failure enforcement remains unresolved | [Evidence and test gate](research/rootfs-signed-content.md) |
| 19 | Offline restore guardrails and backup recheck (#4) | 2026-10-28 | ✅ 24 synthetic tests; all 51 raw/gzip/archive members reverified; hardware follow-up is test 22 below | [Recovery preflight](RECOVERY.md#offline-recovery-preflight-2026-10-28-4) |
| 20 | Read-only USB target and first-write guards (#57) | 2026-10-28 | ✅ 6/6 exact-size, acknowledged reads match backup; 101 MiB; no flash write | [Read rehearsal](research/first-write-plan.md#completed-read-only-rehearsal-2026-10-28) |
| 21 | Patched identical-byte USB rewrite (#70) | 2026-10-28 | ✅ one acknowledged write; 12/12 same-session target/guard reads match; verified stock-B return | [Result and limits](research/patched-identical-write-result.md) |
| 22 | Changed-page USB restore (#72) | 2026-10-29 | ✅ candidate then original; 18/18 exact reads match; verified stock-B return | [Result and limits](research/changed-page-restore-result.md) |
| 23 | Native image written to slot A with the guarded sessions (identical rewrite, then write; base mode from #137) | 2026-10-29 | ✅ five images written; each read-back hash equals the candidate and all neighbour guards match before and after | this page |
| 24 | First boot of slot A, management path | 2026-10-29 | ✅ boots; key-only SSH, LAN, LuCI login | this page |
| 25 | 5G data on slot A | 2026-10-29 | ✅ `wan` up on `ccmni1` with internet; started at boot by `x28-modem` | [NATIVE-CELLULAR](NATIVE-CELLULAR.md) |
| 26 | Services at boot and persistence across reboot | 2026-10-29 | ✅ LuCI, DHCP/DNS, NAT, both Wi-Fi radios; host key, Wi-Fi key and root password unchanged after a reboot | this page |
| 27 | A/B boot counter | 2026-10-29 | ✅ the preloader adds one try per boot (0 → 1 seen); `x28-bootok` writes the byte back to 0 in all four `misc` copies | [BOOT-FLOW](BOOT-FLOW.md) |
| 28 | Download-agent block write to `misc` | 2026-10-29 | ❌ the first block write was not acknowledged, twice; `misc` stayed intact and was verified | this page |
| 29 | Live `misc` byte writes with the stock `dd-nand` | 2026-10-29 | ✅ identical-value test, then A tries 5 → 0 in four copies; the full 1 MiB compared byte for byte after every write | this page |
| 30 | Temperature and idle load on the native image | 2026-10-29 | ✅ SoC 40 °C, CPU 97 % idle (stock: 65 °C idle without fan) | [THERMAL](THERMAL.md) |
| 31 | Proxy tunnel speed and CPU (xray on a local SOCKS port) | 2026-11-01 | ✅ about 0.45 cores per 100 Mbit/s, so an estimated 300–450 Mbit/s ceiling on 4 cores; Passwall2 itself not enabled | [PASSWALL2](PASSWALL2.md) |
| 32 | TPROXY module CRCs against the stock kernel (offline) | 2026-11-01 | ❌ 19 of 35 needed symbols differ and 2 aren't exported; built without CRCs they do load (39) | [kernel-module-crc](research/kernel-module-crc.md) |
| 33 | Soak of slot A | 2026-11-01 | ✅ 26.6 h of the planned 48 h, stopped by the owner: no unexplained restart, WAN up throughout; available memory falls ([#213](https://github.com/mralinp/zlt-x28-openwrt/issues/213)) | this page |
| 34 | opkg stub feed with the image's real opkg (chroot) | 2026-11-01 | ✅ 19 of 19 checks: available stubs/userspace install; incomplete `ipset`, `kmod-nft-core` and `iptables-mod-tproxy` are refused; not yet on a unit | [BUILD](BUILD.md#opkg-feed-for-the-vendor-kernel-200) |
| 35 | Explicit vendor-ipset dependency chain (#200), disposable container | 2026-11-01 | ✅ signed update, invalid-signature rejection, install/remove/reinstall; unchanged upstream payloads; full aggregate refused; not on device | [Evidence](research/vendor-ipset-packaging.md) |
| 36 | X28 opkg feed on the unit (live on 190b, then a clean flash of 219) | 2026-11-02 | ✅ see [section 36](#36-x28-opkg-feed-on-the-unit-2026-11-02); ipset set types and running features not tested |
| 37 | VPN speed and CPU limits, image 219 | 2026-11-02 | ✅ OpenVPN about 100 Mbit/s, limited by one core; WireGuard 715 sending and 330 receiving, CPU not saturated: [section 37](#37-vpn-speed-and-cpu-limits-on-the-router-2026-11-02) |
| 38 | Image with the VPN set on the unit (#230) | 2026-11-02 | ✅ flashed, settings restored, survives a reboot: [section 38](#38-image-with-the-vpn-set-on-the-unit-2026-11-02) |
| 39 | TPROXY and socket modules, and Passwall2 on them (#198) | 2026-11-02 | ✅ 7 modules loaded; Passwall2 with no warnings carries the router's and a LAN phone's TCP, UDP and IPv6 through the UK node: [section 39](#39-tproxy-and-passwall2-on-the-unit-2026-11-02) |
| 41 | Passwall2 throughput from a LAN client | 2026-11-02 | ✅ 206 Mbit/s down, 40 up, router CPU at most 56%: [section 41](#41-passwall2-throughput-from-a-lan-client-2026-11-02) |
| 42 | Boot slot switched to B on the X28 PRO unit: the two priority bytes swapped in the four `misc` copies with `dd-nand` | 2026-11-07 | ✅ written and read back, 8 bytes of the 1 MiB differ; the unit then booted slot B (vendor firmware, key-only SSH on 2222 answered). A USB block write to `misc` was refused again (first block not acknowledged, agent silent afterwards) | [slot-selection](research/slot-selection.md) |
| 43 | DHCP at boot on the X28 PRO unit with `x28-dhcp` (installed by hand on the unit) | 2026-11-07 | ✅ the guard restarted `dnsmasq` 25 s after boot (`x28-dhcp: dnsmasq has no DHCP range for lan; restarting it (1 of 3)`) and the range was served at 34 s, with no manual bridge restart; before it, DHCP stayed dead until the bridge was restarted | [BUILD](BUILD.md) |
| 44 | 5 GHz on the X28 PRO unit with the two-chip capability keys (applied to the Wi-Fi templates by hand on the unit) | 2026-11-07 | ✅ after a reboot `rai0` is on channel 36, the chip reports 64 °C and there are no `FWCmdTimeout` lines (before: temperature 0, 20 timeouts over 30 s, a coredump); the vendor firmware on slot B uses the same keys | [BUILD](BUILD.md) |
| 45 | X28 feed-3 with the image's opkg and on the unit | 2026-11-08 | ✅ 118 checks, 0 failures against the published URL; the unit upgraded its 25 hand-copied modules to the signed `-r1` packages: [section 45](#45-x28-feed-3-with-opkg-and-on-the-unit-2026-11-08) |
| 46 | `x28-kmods` loads the whole module list at boot | 2026-11-08 | ✅ after a real reboot 51 of 51 modules loaded at 30 s of kernel time, the marker cleared and the boot tries returned to `00`; the retry limit refuses with a forced marker: [section 46](#46-x28-kmods-loads-the-whole-module-list-at-boot-2026-11-08) |
| 47 | WireGuard and TPROXY as feed packages: the live feed updated in place, the test unit upgraded | 2026-11-08 | ✅ 132 container checks, 0 failures against the published URL; the unit's invented records became the signed `-r1` packages with identical module files; WireGuard and the TPROXY/socket matches work, also after a reboot: [section 47](#47-wireguard-and-tproxy-as-feed-packages-on-the-live-feed-and-the-unit-2026-11-08) |
| 48 | `x28-kmods` as a package, with the module list in the packages | 2026-11-08 | ✅ 148 container checks, 0 failures against the published URL; on the unit the 28 module packages and the loader were upgraded in one go, the forced marker refused, a live load brought 42 modules back in 3 s, and after a real reboot the loader loaded all 51 by itself: [section 48](#48-x28-kmods-as-a-package-with-the-module-list-in-the-packages-2026-11-08) |
| 49 | The packaged image from the signed feed with 222 packages, on two reflashed units | 2026-11-08 | ✅ both units flashed and boot fast without errors (owner's report); `opkg update` passes every signature; `x28-base` refuses removal of `x28-modem`; 248 container checks, 0 failures: [section 49](#49-the-packaged-image-and-the-feed-with-the-x28--packages-2026-11-08) |
| 50 | Rolling back and forward an x28 package on a unit | 2026-11-08 | ✅ `x28-base` 0.1.0-2 to 0.1.0-1 with `--force-downgrade` and back with `opkg upgrade`; installing from a URL does not work: [section 50](#50-rolling-back-and-forward-an-x28-package-on-a-unit-2026-11-08) |

Inactive `rootfs_sig_a` passed an exact changed-page-and-restore test (22), and the native image then booted from slot A (24). What is not proven: Wi-Fi clients and throughput, a long soak, and any off-device rewrite of `misc` (28).

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

- **Setup**: root SSH to the running X28 (`ssh x28`).
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

## 7. Restore an inactive-slot partition (bounded hardware PASS)

- The [#70 identical rewrite](research/patched-identical-write-result.md) passed one write,
  twelve same-session target/guard reads and a verified stock-B return.
- The separately approved [#72 changed-page test](research/changed-page-restore-result.md) programmed
  exactly one 4 KiB padding page in inactive `rootfs_sig_a`, verified it and every guard, restored the
  original, and verified all six again. Two acknowledged writes, eighteen exact matching reads,
  independent byte comparisons and UART/SSH-confirmed B return passed.
- This proves the narrow tested restore. Arbitrary damaged-target recovery, failed-run restore-only
  re-entry, OOB/bad blocks, damaged-preloader recovery and slot-A/custom-image boot remain unproven.
  Same-Mac backup protection was explicitly disclosed and accepted for these scoped tests.

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

See [RECOVERY: UART](RECOVERY.md#uart-debug-console-2-read-side-confirmed). Shifted RX capture is
confirmed at **921600 8N1**. Pinout on the 3-hole footprint: left board RX, middle GND, right board TX,
all 1.8 V. Board TX at 1.8 V goes through the 1.8-to-3.3 V shifter to adapter RX,
with common GND. The #70 run recorded preloader, DA and the verified stock-B return without
transmitting UART bytes or entering a password. **Do not wire a 3.3 V adapter's TX directly.**

## 16. The 23.05 userspace boots and works (QEMU)

- **Question**: does the userspace we build (fw3 + iptables-legacy instead of firewall4, LuCI from parts)
  actually boot and run, before any device test?
- **Run**: `tools/build/qemu_boot_test.py KERNEL ROOTFS` boots the ImageBuilder's `*-generic-kernel.bin` and
  `*-generic-ext4-rootfs.img.gz` on QEMU `virt` (Cortex-A53, 2 CPUs, 512 MB) over a serial console. In CI it
  runs after every userspace build (so every release is boot-tested). Locally on a Mac:
  ```bash
  docker run --rm -v "$PWD/tools/build:/t:ro" -v "$PWD/private/build/out:/img:ro" debian:bookworm-slim \
    bash -c 'apt-get update -qq && apt-get install -y -qq --no-install-recommends qemu-system-arm curl python3 && \
             python3 -u /t/qemu_boot_test.py /img/openwrt-23.05.5-armsr-armv8-generic-kernel.bin \
                                             /img/openwrt-23.05.5-armsr-armv8-generic-ext4-rootfs.img.gz'
  ```
- **Result** (2026-10-23, Docker on an M-series Mac, software-emulated CPU): booted to the console in 4 s;
  **12/12 checks passed** in 25 s in total:

  | Check | Result |
  |---|---|
  | release, kernel | `armsr/armv8`, `5.15.167` |
  | init | `procd` |
  | netifd | `lan` up, `br-lan` `192.168.1.1/24` |
  | firewall | `/etc/init.d/firewall restart` → `rc=0`; **38** fw3 zone chains |
  | iptables | `iptables v1.8.8 (legacy)`; no `nft` or `fw4` binaries |
  | ubus/rpcd | `system board` reports `23.05.5` |
  | web | `uhttpd` running; LuCI's login page (`<title>OpenWrt - LuCI</title>`, HTTP 403 as LuCI answers unauthenticated requests) through a forwarded port |

- **Gotchas found while writing it**: QEMU's virtio NIC wants a PXE ROM (`efi-virtio.rom`) unless `romfile=`
  is empty; the serial console echoes commands (use `stty -echo` and a split end-marker); OpenWrt's `ip` has no
  `-br`; `uclient-fetch` discards the body on HTTP 403.
- **Not proven**: anything about the X28's own **4.19 kernel** or hardware (QEMU runs 23.05's 5.15 kernel).
  That needs the on-device test (a RAM-only chroot on the running X28) or a flashed slot.

## 17. The 23.05 userspace runs on the X28 (RAM chroot, stock kernel)

- **Question**: do the binaries and services we build work on the X28's own **4.19** kernel, without flashing?
- **Why a chroot**: the stock kernel has no kexec and no net/pid namespaces (only `cgroup`, `mnt`), so a RAM
  boot is impossible and the chroot shares the live network stack. So netifd, `firewall restart` and dnsmasq
  are **not** run (they would take over the router), fw3 only `print`s, uhttpd listens on 127.0.0.1 only, and
  root in the chroot is locked (an rpcd login could reboot or reconfigure the host). An rpcd plugin stands in
  for procd's `system board`, which LuCI's header needs. Reviewed by `router-safety-auditor` before the run.
- **Run** (everything under `/tmp`; the script deletes its tree and the tarball on exit):
  ```bash
  ssh x28 'cat > /tmp/x28-rootfs.tar.gz' < private/build/out/openwrt-23.05.5-armsr-armv8-generic-rootfs.tar.gz
  ssh x28 'sh -s' < tools/build/device_ram_test.sh
  ```
- **Result** (2026-10-23, OEM 1.5.13, kernel 4.19.205, 268 MB available, SoC 50 °C before and after):
  **10/10 checks passed**, twice:

  | Check | Result |
  |---|---|
  | musl binaries on 4.19 | run; release `23.05.5` |
  | uci, opkg | firewall config readable; no `firewall4`/`nftables`/`kmod-nft` installed |
  | iptables | `v1.8.8 (legacy)`, reads the live kernel tables |
  | fw3 | `fw3 -4 print` rc=0, builds the zone chains (`zone_lan_input`, ...) |
  | ubus/rpcd | `session` and `uci` objects answer on the chroot's own socket |
  | web | uhttpd serves LuCI's login page (HTTP 403, `<title>… - LuCI</title>`) |

  Router fingerprint before and after the second run (iptables rules without counters and timestamps, routes,
  addresses, listening ports): **identical**; no files, mounts or processes left; internet up.
- **Gotchas**: `fw3 print` emits `iptables ...` shell commands (running them would apply the ruleset);
  `$!` of a backgrounded shell function is a subshell, not the daemon; under `sh -s` a child reading stdin eats
  the script; `iptables-save` output changes every second (timestamp comment, counters), so strip both to compare.
- **Not proven**: netifd, fw3 *applying* rules, dnsmasq and procd as init on 4.19 (they need the device's network
  to themselves: a flashed inactive slot); Wi-Fi, modem, switch; long-running stability and heat.

## 23–30. The native image on the X28 (slot A, 2026-10-29)

- **Question**: does the image built by `tools/build/` boot from slot A and do the job of a router, and can we keep it
  there safely?
- **Flash** (23): `slot_entry.py rootfs_a identical` then `write` (with `--base-dir` once an earlier image is on slot
  A), each a typed-phrase session with a second backup copy and a live UART capture. Pass criteria the tool enforces:
  the read-back hash of `rootfs_a` equals the candidate, every neighbour partition (boot, lk, tee, signature, `misc`,
  the whole B side and the modem-side partitions) is unchanged before and after, one write, no retry, no reboot.
  Dry runs: `python3 tools/recovery/slot_entry.py rootfs_a identical --candidate-dir <ubi dir> [--base-dir <ubi dir>]`.
- **Boot and router checks** (24–26, 30), read over `ssh x28` and from the Mac:
  `grep bootslot /proc/cmdline`, `ifstatus wan`, `ping 1.1.1.1`, `iptables -t nat -S POSTROUTING`, `wifi status`,
  `curl -d luci_username=root -d luci_password= http://192.168.70.1/cgi-bin/luci` (302 = logged in),
  `/sys/class/thermal/thermal_zone*/temp`, `top`. The reboot test: record the SSH host key and Wi-Fi key hash, `reboot`,
  compare after.
- **Boot counter** (27): read the four copies with `dd if=/dev/mtd3 bs=16 skip=$((128+n*16384)) count=1 | hexdump -C`
  (A priority, tries, success, up-type are bytes 8–11). One try is added per boot; with `x28-bootok` they read 0 again
  once the system is up.
- **Download-agent write to `misc`** (28): `slot_blocks_entry.py misc-blocks confirm --a-retry N --write ...` stopped at
  the first block, twice (`write_result acknowledged: false`). The restore session showed all four copies unchanged. Not
  used again; the `confirm` mode remains in the tree but is unproven on hardware.
- **Live `misc` writes** (29): the stock helper is used exactly as its own boot script uses it,
  `printf '\000' | dd-nand of=/dev/mtd3 seek=<2057 + 262144 × copy> bs=1 count=1`, with the vendor binary copied to `/tmp`.
  An identical-value write came first; after every write all four copies were re-read and the whole 1 MiB compared with a
  dump. Review: router-safety-auditor.
- **Gotchas found**: the preloader counts every boot; a `reboot` without the reset service left the byte at 1; stock B
  repairs (erases) slot A if it ever boots with A's tries above 3; `misc` cannot be rewritten over USB (28); the log
  buffer is flooded by vendor RIL messages, so early boot lines scroll out of `logread`.
- **Not proven**: Wi-Fi client and throughput behaviour, other SIMs, reconnect after a modem reset on
  the final image, and the preloader's fall-back to B (inferred).

## 33. Soak of slot A (2026-10-31 to 2026-11-01)

One read-only sample every 5 minutes, 322 in all, from a logger kept on the router and removed afterwards. It ran 26.6 h of
the planned 48 h: 21.2 h, then the owner's own power or USB disturbance restarted the unit, then 5.4 h. The owner then stopped
it and accepted the behaviour, after daily use as the home connection throughout.

| Measure | Result |
|---|---|
| Unexplained restarts | None. UART shows no panic before the one restart. |
| WAN | Up in every sample |
| Slot A tries | 0 in all four copies, every sample |
| SoC temperature | 36.5–45.4 °C, median 41.5 (test 30: about 40) |
| Load average | 3.00–4.55, median 3.09 |
| `MemAvailable` | 320 → 215 MB, lowest 187, in the first run; 319 → 244 MB, lowest 219, in the second |

**The load average is explained, and harmless.** `ccci_poll1`, `isr_count_polli` and `wed_task0`, vendor kernel threads, are
in uninterruptible sleep in every sample, which counts as 3 of load on a CPU that stays idle. They do not show up as heat.

**Not verified:** a full 48 h, sustained load under heavy traffic, and whether available memory keeps falling or levels off
([#213](https://github.com/mralinp/zlt-x28-openwrt/issues/213)). There is no stock CPU baseline: not measured.

## 36. X28 opkg feed on the unit (2026-11-02)

- **Question**: does the signed `feed-1` feed work on the real unit, and does a freshly flashed image have a working
  package manager with no setup? (#200, #202)
- **Live on 190b**: added the key and feed line by hand, then `opkg update`, `opkg install kernel kmod-tun ipset`, removed
  and reinstalled `kmod-tun`, and rebooted. Everything persisted. LuCI's Software page listed `kernel`.
- **Flash**: `native-ubi-219` over `native-ubi-190b` with `slot_entry.py rootfs_a identical`, a power cycle, then `write`.
  Both receipts read `VERIFIED`, with one write attempt. The first boot reset the overlay.

| Check on the clean image, no setup | Result |
|---|---|
| Rootfs hash, slot, tries | Match the build; slot A; 0 in all four copies |
| `kernel` listed, X28 key and feed present, no `kmod-*` control files | Yes |
| `opkg update` | No errors, feed signature accepted |
| `opkg install ipset`, no `--nodeps` | Installs `1:7.17-1-x28-1` and `x28-ipset-kernel`, and removes and reinstalls cleanly |
| `opkg install kmod-tun tcpdump` | Install |
| `opkg install kmod-nft-core` | Refused, exit 255 |
| Kernel or kmod upgrades offered; packages with 5.15 in the version | None; none |
| `/lib/modules/4.19.205` | Still 146 files |
| `luci-app-passwall2`, `xray-core`, `htop` from their feeds | Install with no force flags, 139 packages in all |
| After one reboot with the settings restored | Slot A, tries 0; packages, config and host key hashes unchanged; 9 signature checks pass; WAN, guest and Wi-Fi up |
| LuCI System → Software | Lists `kernel` |

**Found along the way:**
- The Mac only sees the unit as `MT65xx Preloader` for about a second after power-on. While running, the unit's USB gadget
  reports `not attached` even with a data cable connected, so that state doesn't mean the cable is bad.
- The image's Wi-Fi ships open and root has no password, so a clean unit is open to anyone nearby until it is set up.
- `iwinfo` with no arguments crashed with a segmentation fault on 219. `iwinfo ra0 info` works.
- `ipset --version` warns that the kernel supports protocol 6 and the program 6-7.

**Not verified:** creating ipset sets or the kernel features behind any stub, a Passwall2 run on this image, and the UART
shell's transmit line. Restoring a saved overlay as a whole would hide the new `opkg` state, so settings were restored file
by file.

## 37. VPN speed and CPU limits on the router (2026-11-02)

- **Question**: how fast can OpenVPN and WireGuard go on this device, and what limits them?
- **Setup**: image 219, slot A, UDP. `iperf3` for 20 s per test, once per setup, between the router and a Docker peer on a LAN
  laptop behind another router. No cellular data. The router's `iperf3` ran from RAM. OpenVPN is the feed's 2.5.8 with mbed TLS.
  WireGuard is `wireguard-linux-compat` 1.0.20220627 built from the SDK tree and loaded from RAM, with no symbol version
  check ([#227](https://github.com/mralinp/zlt-x28-openwrt/issues/227)).

| Test | Router sends | Router receives | Total CPU (4 cores) |
|---|---|---|---|
| No tunnel | 856 Mbit/s | 363 Mbit/s | 9% / 36% |
| WireGuard | 630 Mbit/s | 268 Mbit/s | 51% |
| WireGuard, 4 streams | 715 Mbit/s | 330 Mbit/s | 55–58% |
| OpenVPN AES-128-GCM | 102 Mbit/s | 58 Mbit/s | 24–27% |
| OpenVPN AES-256-GCM | 98 Mbit/s | 59 Mbit/s | 24–27% |
| OpenVPN ChaCha20-Poly1305 | 77 Mbit/s | 75 Mbit/s | 26% |

With 4 streams, OpenVPN sent 95–101 Mbit/s with AES and 91 with ChaCha20. SoC temperature stayed at 45–48 °C, with no kernel
errors in `dmesg` or on UART.

The OpenSSL build of the same OpenVPN version (`openvpn-openssl`, OpenSSL 3.0.18), run from RAM in a later session:

| Test | Router sends | Router receives | Total CPU (4 cores) |
|---|---|---|---|
| OpenVPN OpenSSL AES-256-GCM | 74 Mbit/s | 84 Mbit/s | 25–27% |
| OpenVPN OpenSSL AES-128-GCM | 75 Mbit/s | 82 Mbit/s | 25–27% |
| OpenVPN OpenSSL ChaCha20-Poly1305 | 75 Mbit/s | 82 Mbit/s | 26–27% |
| Control: mbed TLS AES-256-GCM, same session | 90 Mbit/s | 52 Mbit/s | 23–26% |

With 4 streams, OpenSSL AES-128-GCM sent 85 Mbit/s. A router-side client download is the "router receives" column, where OpenSSL is
faster; uploads are slower. All three ciphers run at the same speed under OpenSSL, which suggests encryption is not its limit;
the single thread moving packets through the tun device is the likely one, but this was not profiled.

**Reading the results:** OpenVPN is limited by one CPU core: 25% of total CPU is one full core, and more streams don't help.
WireGuard uses all four cores and stayed under 60%, so its limit was not reached. Receive results are capped by the path from
the laptop, which carries about 365 Mbit/s with no tunnel.

**Not verified:** LAN clients forwarded through a tunnel, which adds NAT and routing cost; a tunnel across the carrier; other
OpenVPN builds; and long-term WireGuard stability.

## 38. Image with the VPN set on the unit (2026-11-02)

- **Question**: does the image from #230 boot and serve the LAN, and does the WireGuard loader behave on a clean flash?
- **Flash**: `native-ubi-234b` over 219 with `slot_entry.py rootfs_a identical`, a power cycle, then `write`. Both receipts read
  `VERIFIED`, with one write attempt. The rootfs hash after boot matched the build; the overlay was reset on first boot.
- **Restore**: settings from a fresh overlay backup, one file at a time (password, network, DHCP, firewall, Wi-Fi, Passwall2,
  LuCI and cron configs, SSH host keys). Passwall2, `xray-core`, `ipset`, `tcpdump`, `htop` and `kmod-tun` were reinstalled with
  `opkg` and no force flags. `opkg` state and the old feed line were not restored, so the image's own stay in use.

| Check, after one reboot with settings restored | Result |
|---|---|
| Slot, tries | A; 0 in all four copies |
| Settings and SSH host key hashes, installed packages | Unchanged (154 packages) |
| `dnsmasq-full` | Running with `ipset no-nftset`; DNS answers, DHCP serves the LAN |
| WireGuard | Module loaded after the tries were reset, crash marker cleared; `wireguard`, `l2tp` and `pptp` protocols in netifd |
| WAN, guest network, Wi-Fi | Up |
| `opkg update` | 9 signature checks pass; no kernel, kmod or `dnsmasq` upgrade offered |
| Kernel errors | None in `dmesg` or on UART |

**Found:** Wi-Fi is open and root has no password for the first minutes of a clean flash, by design, until settings are
restored. Restoring the old SSH host keys switches the served key at once, so the next connection in a script sees a
changed key.

**Not verified:** L2TP and PPTP against a server, OpenVPN with a provider, Passwall2 enabled, and WireGuard over hours
([#227](https://github.com/mralinp/zlt-x28-openwrt/issues/227)).

## 39. TPROXY and Passwall2 on the unit (2026-11-02)

- **Question**: do TPROXY and socket modules built from the SDK tree load and work on the stock kernel, and does Passwall2
  then run without errors?
- **Build**: `nf_socket_ipv4/6`, `nf_tproxy_ipv4/6`, `xt_socket` and `xt_TPROXY` from the `x28-kbuild` tree, plus
  `x28_udp_lookup`, which supplies the `udp4_lib_lookup` and `udp6_lib_lookup` the stock kernel never exported (upstream
  bodies on the exported `__udp4/6_lib_lookup`). No `Module.symvers`, as for WireGuard (#227).
- **Offline**: every needed symbol is exported by the stock kernel or its loaded modules. Of the 15 CRC-differing functions
  that could be compared, 12 use the same struct offsets; the other 3 only looked different because the scan window
  ended early, and the stock code makes the same loads further on.
- **Live**: loaded from `/tmp` after the boot tries were reset, then `iptables-mod-tproxy`, `-socket` and `-extra` with
  `--nodeps`. Passwall2 with `tcp_proxy_way=tproxy`, `localhost_proxy=1`, `client_proxy=0` and the UK node.

| Check | Result |
|---|---|
| `insmod` of the 7 modules | All loaded; no oops or warning in `dmesg`; taint unchanged (4097, from WireGuard) |
| Passwall2 start | Rules loaded; 0 warnings and 0 errors in its log once `prefer_nft=0` |
| TCP from the router | Through `socket --transparent` and TPROXY; exit `GB` |
| UDP from the router | NTP to `162.159.200.1` answered with about 200 ms delay; the TPROXY UDP counter rose |
| DNS | Through Passwall2's dnsmasq and xray |
| SoC | 41 °C |

**LAN round**, with `client_proxy=1` and `ipv6_tproxy=1`, a 15-minute auto-rollback armed, and the owner switching it on in
LuCI:

| Check | Result |
|---|---|
| Switch in LuCI | Saved but not applied at first: `ucitrack` wasn't running (the image drops its boot link) and Passwall2's init script had been disabled. Fine after starting `ucitrack` |
| Phone on X28 Wi-Fi | Worked for the owner; 233 xray connections from it |
| LAN TCP and UDP | 560 TCP and 1,124 UDP packets through the LAN TPROXY rules; about 25 MB through xray's transparent sockets |
| LAN IPv6 | Through the IPv6 TPROXY rules, 3 xray connections from a LAN IPv6 address |
| Kernel, SoC | No messages; 40 °C |

The Linksys behind this unit kept its own tunnel to the same node; the X28 passes that connection straight out (`psw2_vps`),
so it isn't wrapped twice.

**Reboot**, with the modules in `/lib/modules/4.19.205`, `x28-kmods` in place of `x28-wireguard`, and `ucitrack` enabled:
SSH back after about 60 s; boot tries `00` in all four copies; all 8 modules (WireGuard included) loaded by 66 s and the
crash marker cleared after 120 s. Passwall2's own delayed start finished at 60 s, and `x28-kmods` restarted it once
TPROXY was in, with IPv4 and IPv6 LAN rules, no warnings and no kernel messages. `ucitrack` registered the `passwall2`
reload trigger.

The modules were then moved to `/lib/modules/x28` (a safety review found that the kernel's `modprobe` could load them from
`/lib/modules/4.19.205` on its own, bypassing the crash marker); booting from there is not yet tested.

**Not verified:** switching it off from LuCI with `ucitrack` running, LAN throughput, the modules over hours, and the image
built with them (#198).

**Later the same day (#239):** LuCI's Passwall2 page showed the core running and its Baidu, Google and GitHub checks
answered through the node ([screenshot](PASSWALL2.md)); `ipinfo.io/country` on the router answered the node's country.

## 40. Passwall2 LAN kill switch with direct ICMP (2026-11-02)

Issue: #251. Owner-approved live deployment on the native OpenWrt 23.05.5 / vendor 4.19.205 unit, plus clean-rootfs
integration tests. The previous unit-local guard rejected ping. Linksys allowed it directly over its phone uplink,
not through Xray. The replacement intentionally allows direct ICMP while rejecting other direct cellular forwarding.

| Check | Result |
|---|---|
| `python3 tools/build/test_first_boot.py` | 11 tests pass; generated rootfs contains exact script, mode 0755, fw3 include and hooks before all start/stop/restart calls; Passwall2 defaults off |
| `python3 tools/build/test_killswitch.py` | Stateful fake iptables/ip6tables: enabled, repeated apply, disabled, re-enabled and simulated firewall rebuild; no duplicate rules or enabled-chain flush |
| `sh -n tools/build/x28-killswitch.sh`; `git diff --check` | Pass |
| Live `/etc/x28-killswitch.sh` applied twice | One jump and one non-ICMP `ccmni+` reject per IP family; no service restart |
| Live Passwall2 | `enabled=1`, Xray process remains running |
| Laptop via `192.168.70.1`: `ping -c 3 google.com` | 3/3 replies, no loss; ICMP intentionally direct |
| Laptop: `curl -I https://www.google.com` | HTTP/2 200 with guard active; this alone does not prove the proxy exit |

Before deployment, config, script, init script and both firewall rule snapshots were backed up under
`/root/killswitch-251-20261102-163502` and each checked non-empty. No firmware write, reboot, modem command,
LAN change or network/firewall/Passwall2 restart was performed. Clean-image integration is in `first_boot.py`;
this is not evidence of booting a newly flashed image.

**Rollback on this unit** (returns to the prior disabled extra guard without a networking restart):

```sh
iptables -F x28_killswitch
ip6tables -F x28_killswitch
b=/root/killswitch-251-20261102-163502
cp -p "$b/firewall" /etc/config/firewall
cp -p "$b/x28-killswitch.sh" /etc/x28-killswitch.sh
cp -p "$b/passwall2" /etc/init.d/passwall2
```

**Safety review:** shell and router-safety checklists reviewed: only the filter FORWARD custom chain is hooked;
LAN addressing, SSH/authentication, INPUT/OUTPUT rules and boot partitions are untouched. The guard runs before
Passwall2 tears down its rules and stays active if the service stops while UCI still says enabled. Both families
must apply successfully or the script returns an error. ICMP and router-originated traffic remain explicit bypasses.
Passwall2 upgrades can overwrite the init hooks; see [PASSWALL2](PASSWALL2.md#lan-kill-switch).

**Not verified:** actual clean flash/boot, reboot persistence on hardware, real firewall reload or LuCI off/on,
tunnel-down behavior, end-to-end IPv6 and exhaustive traffic/leak tests. No independent safety-agent run was available;
the checklists were applied in-session. The kill switch covers the cellular `ccmni+` WAN, not future Ethernet/VPN uplinks.

## 41. Passwall2 throughput from a LAN client (2026-11-02)

- **Question**: how fast is Passwall2 for a device on the LAN, and how loaded is the router while it runs?
- **Setup**: slot A with Passwall2 on (xray, VLESS over XHTTP with TLS, TPROXY), the LAN kill switch of section 40 on.
  A Mac on Wi-Fi behind a second router, which itself is an X28 LAN client with its own proxy off. Apple's
  `networkQuality -s` (sequential download then upload, 12 and 16 flows, Apple's London edge). The router's `/proc/stat`
  and xray's CPU time sampled every 2 s over SSH during the run.

| Direction | Throughput | Router CPU (4 cores), peak | xray, peak |
|---|---|---|---|
| Download | 206 Mbit/s | 56% | 1.1 cores |
| Upload | 40 Mbit/s | | |

The test's exit was the node's (GB), not the ISP's. The SoC was at 44.7 °C right after. At 1.1 cores for about 200 Mbit/s
this agrees with the 0.45 cores per 100 Mbit/s of section 31, so the router was not the limit; the cellular link, the
node and the second router's Wi-Fi share what is left.

**Not verified:** a client wired straight to the X28, and a link fast enough to reach the CPU ceiling.

## 45. X28 feed-3 with opkg and on the unit (2026-11-08)

- **Question**: does the published, signed feed (209 packages: the `kernel` record, 180 stubs, 25 packages that carry our built
  modules, 3 vendor ipset) work with the image's own `opkg`, and does it replace the modules copied to the unit by hand?
- **Setup**: `tools/build/opkg_real_test.sh` runs the image's `opkg` (rootfs of build 264) in a throwaway chroot on an arm64
  Docker host, official feeds on, against `https://github.com/mralinp/zlt-x28-openwrt/releases/latest/download` with the key
  the image ships (no temporary key). Then the same URL on the test unit (slot A, kernel 4.19.205).

| Check | Result |
|---|---|
| The image ships key `7fec994ab0d15b97`; `opkg update` passes the signature check; the index lists 209 packages | ✅ |
| Each of the 25 built packages installs as `1:4.19.205-x28-r1`; every module file equals the build output (44 file checks); the dependency-only `kmod-sched-connmark` carries no files | ✅ |
| `tc-full`, `sqm-scripts`, `ss`, `iptables-mod-hashlimit`, `iptables-mod-ipsec`, `nbd`, `usbip`, `proto-bonding` install from the official feed | ✅ |
| `kmod-nft-core`, `iptables-mod-quota2`, `open-iscsi` and the incomplete `kmod-ipt-ipset` are refused; `ipset` installs through the vendor subset | ✅ |
| No 5.15 `kmod-*` installed or offered as an upgrade | ✅ |
| The hand-copied `1:4.19.205-x28` kmod-sched-core is offered as an upgrade and becomes `-r1` | ✅ |
| **On the unit**: the feed line moved to the stable URL, `opkg update` passes the signature, exactly the 25 hand-copied packages are offered, `opkg upgrade` makes all 25 `-r1`, nothing is left to upgrade, and all 43 module files equal the signed build | ✅ |
| After the upgrade, `sch_cake` shaped traffic on a throwaway veth pair and an `act_gact` drop action dropped its packets; no reboot (up 5:17), no oops in `dmesg` | ✅ |

Result: 118 checks, 0 failures in the container. Reproduce:

```sh
docker run --rm --cap-add MKNOD -e FEED_URL=https://github.com/mralinp/zlt-x28-openwrt/releases/latest/download \
  -v ROOTFS_DIR:/in:ro -v KMODS_DIR:/kmods:ro -v OLD_DIR:/old:ro \
  -v "$PWD/package/x28-kmod-stubs/real.txt:/real.txt:ro" -v "$PWD/tools/build:/t:ro" debian:stable-slim bash /t/opkg_real_test.sh
```

The modules themselves were tested one by one on the unit while they were built (loading, traffic shaping, tc actions and
filters, bonding, iptables matches, `ss` through netlink and raw diag, AF_ALG sockets, and the RFC 7539 ChaCha20-Poly1305 vector).

**Not verified:** loading all the modules at boot through `x28-kmods` (needs a reflashed image and a reboot); `nbd`,
`spidev`, `cdc-acm` and USB/IP against real servers or hardware; a real IPsec tunnel with ChaCha20-Poly1305; `sch_multiq`
and the `text` ematch (not exercised by the available tools).

## 46. x28-kmods loads the whole module list at boot (2026-11-08)

- **Question**: with the 25 packages from the feed installed, does `x28-kmods` load all 51 modules of its list (the 8 of the image and
  our 43) by itself after a reboot, without harm, and does its safety net hold?
- **Setup**: the test unit (slot A, kernel 4.19.205, the 25 packages at `1:4.19.205-x28-r1` from [test 45](#45-x28-feed-3-with-opkg-and-on-the-unit-2026-11-08)).
  The unit's image has the older script (8 modules), so the new `package/x28-kmods/files/x28-kmods.init` from `main` was copied
  to `/etc/init.d/x28-kmods` (the old one saved in `/root/`). Slot A boot tries `00 00 00 00` and no marker before each phase.

| Phase | Result |
|---|---|
| 1. Marker set to `3`, loader started | ✅ refused, logged "3 loads in a row did not finish; not loading", loaded none of the new modules |
| 2. Marker removed, `/etc/init.d/x28-kmods start` on the running unit | ✅ 51 of 51 modules loaded within 10 s; marker `1` during the load and cleared after about 115 s; no `oops`, `bug` or `unknown symbol`; LAN, internet and services unaffected |
| 3. `reboot` | ✅ SSH back within about 70 s on slot A; `x28-kmods` loaded 51 of 51 by itself (kernel time 30.5 s to 31.1 s, right after `x28-bootok`); marker cleared at about 150 s; boot tries `00 00 00 00`; ping 109 ms; `dnsmasq`, `dropbear`, `uhttpd`, `netifd` running, LuCI answers; Wi-Fi (`ra0`, `rai0`) and cellular (`ccmni1`) up |

Side effects, as on stock OpenWrt: loading `bonding` and `dummy` creates idle `bond0` and `dummy0` (DOWN), `nbd` creates 16 `/dev/nbd*`
nodes, taint becomes 4097. Free memory fell by about 8 MB at most. The only `dmesg` line matching "panic" is
"Disabling lock debugging due to kernel taint" from the vendor's own modules at 15 s (the log tag contains the word).

Reproduce (on the unit, after copying the script):

```sh
echo 3 > /etc/x28-kmods.loading; /etc/init.d/x28-kmods start; sleep 10; logread | grep x28-kmods; rm /etc/x28-kmods.loading   # phase 1
/etc/init.d/x28-kmods start; sleep 10; ls /sys/module | wc -l                                                              # phase 2
reboot                                                                                                                     # phase 3
```

**Not verified:** a reflashed image that carries this script (the same file, so no difference is expected); `nbd`, `spidev`, `cdc-acm` and USB/IP
against real servers or hardware; a real IPsec tunnel with ChaCha20-Poly1305; a module that crashes the kernel at boot (the
marker's retry limit was tested only with a forced marker, not with a real crash).

## 47. WireGuard and TPROXY as feed packages, on the live feed and the unit (2026-11-08)

- **Question**: after `kmod-wireguard`, `kmod-ipt-tproxy` and `kmod-ipt-socket` became feed packages (#415) and the one feed
  release was updated in place, do they install from the published URL, and does the test unit's invented record become the
  real package without changing the module files?
- **Setup**: the feed (212 packages) signed on the owner's Mac and the release updated in place: the 3 new packages uploaded
  first, the index files replaced last (the other 209 packages were already identical). Then the test unit (slot A, kernel
  4.19.205, boot tries `00 00 00 00`), after an opkg status backup.

| Check | Result |
|---|---|
| Served `Packages` equals the pin (`caab74a2…`), lists 212 packages, signature verifies with the committed key, the three new packages match the index | ✅ |
| The image's `opkg` against the published URL with the key the image ships: update, signature, 212 in the index, 28 built packages install with their files equal to the build, consumers, refusals, upgrade from the hand-copied build | ✅ 132 checks, 0 failures |
| The image's records for the three packages are `1:4.19.205-x28` before and `1:4.19.205-x28-r1` after | ✅ |
| On the unit: `opkg list-upgradable` offered exactly the three; `opkg upgrade` made them `-r1`; the 8 module files are byte-identical to before; `opkg files` lists them under the packages; the modules stayed loaded; nothing left to upgrade | ✅ |
| On the unit: a WireGuard interface can be created, keyed with a listening port and removed; the `socket` match and the `TPROXY` target are accepted in a throwaway chain; internet up, no `oops` in `dmesg` | ✅ |
| After a real reboot of the unit: back in about 24 s on slot A; `x28-kmods` loaded all 51 modules (first sample at uptime 96 s), marker cleared at about 153 s; boot tries `00 00 00 00`; the three packages still `-r1` and the 8 module files with the same digest as before; all 8 modules loaded; WireGuard and the `socket`/`TPROXY` checks repeated and passed; LAN, Wi-Fi, cellular, `dnsmasq`, `dropbear`, `uhttpd`, `netifd` up; no `oops` | ✅ |

**Not verified:** Passwall2 end to end on the upgraded packages (it is off on the unit, and enabling it routes the unit's traffic
through a node; it was tested on the same module files in [test 39](#39-tproxy-and-passwall2-on-the-unit-2026-11-02)); the image still bakes
these modules and invents their records until the flasher installs packages (#420).

## 48. x28-kmods as a package, with the module list in the packages (2026-11-08)

- **Question** (#416): does the loader work as a feed package that reads each module package's list, installing over the image's old
  script, and does it still load everything safely at boot?
- **Setup**: the feed (213 packages) updated in place; the image's `opkg` in a container against the published URL; then the test
  unit (slot A, tries `00 00 00 00`), after an opkg status backup and a copy of the loader it ran (`/root/x28-kmods.init.prev`).

| Check | Result |
|---|---|
| Container, live URL, key the image ships: the loader installs over the image's unowned script (no forced overwrite), is owned and enabled (S97 link), `modules` lists 51 modules once each in dependency order; removing `kmod-nbd` removes its list and its module from the load, reinstalling brings it back; removing the loader removes the boot link and script, reinstalling enables it | ✅ 148 checks, 0 failures (twice in a row; two earlier runs hit intermittent downloads) |
| Unit: `opkg upgrade` of the 28 module packages to `-r2` and `opkg install x28-kmods`; 27 list files; the script equals the repo's; nothing left to upgrade | ✅ |
| Unit, forced marker `3` with 42 modules unloaded: the loader refuses, logs "3 loads in a row did not finish; not loading", loads nothing | ✅ |
| Unit, live load: all 51 loaded within 3 s; marker `1` during the load, cleared after its window; boot tries `00 00 00 00`; no `oops`, `bug` or `unknown symbol`; internet up | ✅ |
| Unit, real reboot: back in about 24 s on slot A; the loader loaded all 51 by itself (kernel time 30.6 s to 31.2 s, first sample at 90 s already 51); marker cleared at about 155 s; tries `00 00 00 00`; 29 packages at `-r2`, nothing to upgrade; WireGuard and the `socket`/`TPROXY` checks pass; LAN, Wi-Fi, cellular, `dnsmasq`, `dropbear`, `uhttpd`, `netifd` up; no `oops` | ✅ |

The container test found a builder bug before any of this: the `.ipk` data archives had no directory entries, and opkg does not create
missing parent directories (it prints `wfopen: ... No such file or directory`, exits 0 and records the file), so a package could not
install into a directory the image lacks. Every data archive now carries its parent directories, and the test fails on opkg's error lines.

**Not verified:** a freshly flashed image built from packages (the flasher still bakes the modules and the old script until #420); a
unit with the new loader but only some module packages upgraded (the migration upgrades everything in one command before the reboot);
the `-r1` files still on the release (kept until this passed; they are not in the index).

## 49. The packaged image and the feed with the x28-* packages (2026-11-08)

- **Question**: does the signed feed with the x28-* packages and `x28-base` (222 packages, [#423](https://github.com/mralinp/zlt-x28-openwrt/issues/423)) work with the image's own `opkg`, and does an image built from those packages run on real units?
- **Setup**: the feed was built with `vendor_ipset.py --x28-packages`, checked against the release ipks with `release_check.py compare` (`ok`), signed offline and published in place (Packages `2935ebb8…48d6`). The image was built by the flasher at `87dbdf0` (packaged mode, mralinp/x28-flasher#73) from the release bundle. Both units were flashed by the owner with the guarded tools.

| Check | Result |
|---|---|
| The published `Packages` has the pinned SHA-256; the signature verifies with the repo's public key; `compare` against the live URL is `ok` | ✅ |
| The image's real `opkg` in a container against the live URL: signature, 222 packages, each x28-* package installs with files equal to the repo sources, modes and boot links right, module packages and refusals as before, the hand-copied `kmod-sched-core` upgrades: **248 checks, 0 failures** | ✅ |
| Both units flashed with the packaged image: fully functional, fast boots, no errors (owner's report; the details were not collected here) | ✅ |
| On a flashed unit, `opkg update` passes the signature check on our feed and every other feed | ✅ |
| On a flashed unit, `opkg remove x28-modem --noaction` is refused: `x28-base` depends on it; `--force-depends` is the named override | ✅ |

**Not verified:** (the upgrade and the rollback are now covered by test 50) a reboot after upgrading
a boot-critical package that is not `x28-kmods`; the full package list on the flashed units (not collected); the flasher's CI release (its runs were cancelled).

## 50. Rolling back and forward an x28 package on a unit (2026-11-08)

- **Question**: does the rollback described in [PACKAGE-FEED](PACKAGE-FEED.md) work, and does `opkg upgrade` of an x28-* package from the live feed work on a unit?
- **Setup**: the test unit (flashed with the packaged image; `x28-base` 0.1.0-2, `x28-nrband` and `x28-switch` installed by hand from the live feed).

| Step | Result |
|---|---|
| `opkg install --force-downgrade <URL of x28-base_0.1.0-1_all.ipk>` | ❌ `wfopen: …: No such file or directory`: this `opkg` cannot install from a URL; the unit was not changed |
| Download the file to `/tmp` with `uclient-fetch`: SHA-256 equals the release build | ✅ |
| `opkg install --force-downgrade /tmp/x28-base_0.1.0-1_all.ipk` | ✅ `x28-base` 0.1.0-1, its `Depends` back to the earlier list, `x28-nrband` and `x28-switch` and their files untouched, no reboot |
| `opkg update && opkg upgrade x28-base` | ✅ offered `0.1.0-1 - 0.1.0-2`, installed `0.1.0-2` from the live feed, `Depends` list with `x28-switch` and `x28-nrband`; nothing left to upgrade |
| After: no `oops` or `unknown symbol` in `dmesg`; up 1:33, never rebooted | ✅ |

**Not verified:** rolling back a boot-critical package (`x28-bootok`, `x28-modem`) and rebooting; a rollback on the second unit; the band tool itself (not run).
