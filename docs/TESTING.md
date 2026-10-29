# Test log

Everything this project has tested, what it proved, how to run it again, and what it did **not** prove.
Written for whoever picks this up later with no memory of the sessions: start here before trusting a claim
anywhere else in the repo.

Conventions:
- **Device**: one ZLT X28, kernel 4.19.205. Tests 1–22 ran on the stock firmware (OEM 1.5.13, OpenWrt 19.07-derived, active slot **B**); tests 23–30 ran on the native image on slot **A**.
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
confirmed at **921600 8N1**: board TX at 1.8 V through the 1.8-to-3.3 V shifter to adapter RX,
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
  ssh router 'cat > /tmp/x28-rootfs.tar.gz' < private/build/out/openwrt-23.05.5-armsr-armv8-generic-rootfs.tar.gz
  ssh router 'sh -s' < tools/build/device_ram_test.sh
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
- **Boot and router checks** (24–26, 30), read over `ssh router` and from the Mac:
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
- **Not proven**: Wi-Fi client and throughput behaviour, a multi-day soak, other SIMs, reconnect after a modem reset on
  the final image, the preloader's fall-back to B (inferred), and the load average of about 3 with an idle CPU.
