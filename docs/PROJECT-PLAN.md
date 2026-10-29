# ZLT X28: custom OpenWrt project plan

Goal: an optimized, modern OpenWrt for the ZLT X28 (MediaTek MT6890 / T750, 4x Cortex-A55), with a fully
working stock LuCI, cooler operation, and local SMS and voice for an AI project.

> **Current state:** [STATUS.md](STATUS.md). **Evidence:** [TESTING.md](TESTING.md). **History:** [CHANGELOG](../CHANGELOG.md).
> This plan was written on 2026-10-20 and brought up to date on 2026-10-29; facts learned since are marked *(updated)*.

## What we know (measured on the device, 2026-10-20)

| Item | Fact |
|---|---|
| Base | OpenWrt 19.07-SNAPSHOT, target `mt6890/evb6890v1_64_cpe_nand`, arch `aarch64_cortex-a55_neon-vfpv4`, kernel 4.19.205, musl |
| Flash | NAND, 51 mtd partitions. **A/B slots**: `lk_a/b`, `boot_a/b`, `rootfs_a/b`, `md1img_a/b` (modem), `tee_a/b` |
| Rootfs | squashfs (`/rom`) + UBIFS overlay (22.8 MB, `/overlay`); `rootfs_sig_a/b` and `seccfg` partitions present. *(updated)* Preloader reports secure boot (SBC), SLA and DAA **off** |
| Data | `user_data` (~440 MB UBIFS: `/customer`, `/data`), vendor config in `nvram`, `nvdata`, `nvcfg` |
| Packages | 346 installed; vendor 4.19 kernel modules in `/lib/modules/4.19.205` (WiFi `conninfra`, BT, etc.) |
| Netifd | proto scripts exist (`ql_mipc`), so the original design used netifd; vendor replaced it with `ql_netd`, `firewalltools`, `lan_mgr` |
| Thermal | no fan; SoC ~65 C idle; kernel trips 85/95/115 C; Quectel `ql_ntc` policy is a separate, hidden limit |
| Kernel cmdline | `initcall_debug=1 loglevel=8` (verbose debug logging left on) |
| Public support | none official. *(updated)* Community: [mt6890-cpe-recovery](https://github.com/mt6890-cpe-recovery/mt6890-cpe-recovery) (SP Flash Tool package with a Quectel DA), [gaglians/zlt-x28-openwrt2305](https://github.com/gaglians/zlt-x28-openwrt2305) (23.05 userland on the vendor kernel; needs the vendor SDK) |

## Strategy

Stay on the vendor kernel and blobs (modem, WiFi, TEE, audio). Rebuild only the userland as a modern OpenWrt.
Migrate in stages so the box stays usable after every stage.

- **Stage 1: adapter layer (superseded).** Vendor daemons stay, UCI is synced to the vendor backend via `vendorbridge`/`vendorsync` on the stock firmware (`router/`). It worked, but it is not the goal; the native image does not use it.
- **Stage 2: take over networking (done on slot A).** Real `netifd`, the firewall and `dnsmasq`, with the modem WAN through our own `x28_mipc` protocol; the vendor network managers are gone. *(updated)* The stock kernel has no `nf_tables`, so the firewall is **fw3 + iptables-legacy**, not fw4.
- **Stage 3: rebuilt rootfs (done on slot A).** OpenWrt 23.05.5 userland (musl, aarch64) on the vendor kernel and its modules, flashed to the inactive A/B slot with guarded tools. *(updated)* It boots on one unit with 5G, LuCI, LAN, Wi-Fi and LEDs ([STATUS](STATUS.md)).
- **Stage 4: stable release with a recovery slot (next).** See the roadmap below.

## Phase status (2026-10-29)

| Phase | State |
|---|---|
| 0 Safety | ✅ backup verified, USB recovery and UART working, guarded `rootfs_a` write and restore proven; `misc` rewrite over USB unproven |
| 1 Stabilise and cool | 🟡 about 40 °C idle on the native image; the CPU/RAM baseline and a 48 h soak are still to do |
| 2 Stock options (adapter) | ⏹️ superseded by the native image; kept only as history |
| 3 SMS and voice | 🗓️ worked on the stock overlay; to be ported to the native image |
| 4 Source and toolchain | 🟡 stock blobs extracted and used; GPL source not obtained; own kernel parked ([#130](https://github.com/mralinp/zlt-x28-openwrt/issues/130)) |
| 5 Modern OpenWrt image | ✅ boots on slot A with LAN, Wi-Fi and cellular data; stock slot B untouched |
| 6 Release | 🟡 pre-releases on every merge; stable release, recovery slot and `sysupgrade` still ahead |

## Phases

### Phase 0: safety (must come first, nothing flashed)
1. Full dump of every mtd partition (`nanddump`, keep checksums) plus `user_data`. Store off the device.
2. UART access: find the pads, clip a TTL adapter, capture the boot log (921600 8N1), find the LK/bootloader prompt. *(updated)* The logic level may be **1.8 V**: measure before wiring, and never drive a 1.8 V pin from a 3.3 V adapter's TX.
3. Document recovery: how `lk_a/b` selects a slot, fastboot or MTK download mode, what the `seccfg` lock state is.
4. Decide on a sacrificial second unit if possible.
Done when: dumps verified, UART boot log captured, one tested way back to stock.

### Phase 1: stabilise and cool (runtime-only, reversible)
1. Temperature and uptime logger that survives reboot, to settle the heat vs. other-causes question.
2. Cap CPU max frequency, change the governor, lock the Ethernet PHY to 1G if 2.5G is not needed; measure.
3. Remove or stop debug daemons (`mdlogger`, `aee_aed`, extra HTTP servers); measure idle load and temperature.
Done when: idle temperature and CPU load measured before/after, no unexplained reboots over 48 h.

### Phase 2: stock options working (adapter layer)
1. `vendorsync` import/export for DHCP/DNS, firewall port forwards and DMZ, then network and wireless.
2. ucitrack hooks, boot import, selftest, LuCI Save & Apply loop.
3. Fix LuCI (stock Overview errors, hide only what truly can't map).
Done when: the stock LuCI pages for LAN, DHCP, port forwards and DMZ change the real router.

### Phase 3: SMS and voice for the AI project
1. SMS API (HTTP/MQTT/ubus) on top of the bridge: send, receive webhook, queue, rate limit.
2. Voice: needs a voice-capable SIM path (VoLTE provisioning or CS fallback). Then call control (`voicectl`) and audio: probe `/dev/snd` PCM, modem AFE, `libqlaudio`.
3. Decide how the AI hears and speaks on a call (PCM tap, SIP bridge via `siproxd`, or external gateway).
Done when: SMS in/out is automatable, and a call can be placed or answered with an audio path to software.

### Phase 4: source and toolchain
1. Request the GPL source in writing from ZLT/Tozed (kernel 4.19 and the OpenWrt tree are GPL; vendor must provide on request).
2. Extract blobs from the stock image (modem libs, WiFi firmware, `libql*`, `libmipc*`), record versions.
3. Reproduce the stock rootfs with an OpenWrt buildroot using an external toolchain matching musl and the cortex-a55 ABI.
Done when: a rootfs built from our tree boots in the inactive slot and reaches the same state as stock.

### Phase 5: modern OpenWrt image
1. New target in buildroot with the vendor kernel and kmods; strip debug options.
2. Modern userland: netifd, fw3 (iptables-legacy; the stock kernel has no nftables), dnsmasq, LuCI, rpcd, our adapter retired in favor of native config.
3. Flash to the **inactive** slot (slot A on this unit, which ran B), select it with the A/B boot record, keep the other slot as stock fallback. *(updated)* Done: slot A runs the native image.
4. Fix the signed-rootfs question (`rootfs_sig`, `seccfg`): check whether the unlocked unit accepts unsigned images. *(updated)* No rootfs content check was found in LK or the kernel, and the image boots; see [BOOT-FLOW](BOOT-FLOW.md).
Done when: the inactive slot boots OpenWrt with working LAN, WiFi and cellular data, and the stock slot is untouched. *(updated)* Met on 2026-10-29.

### Phase 6: release
Reproducible build (CI), versioned images, upgrade path (slot switch), docs, a recovery guide. *(updated)* The roadmap below is how this phase gets done.

## Roadmap to a stable release (2026-10-29)

Target layout: **slot A holds a stable OpenWrt, slot B becomes a recovery slot**. The recovery slot is a small kernel
and rescue path that can install or reinstall OpenWrt on slot A and can put the stock firmware back. Today both slots
hold a full firmware; with a recovery slot the second full firmware is no longer kept, which frees storage, and
everyday recovery no longer needs the download agent and a UART. The download-agent route stays as the last resort.

1. **Stabilise slot A.** 48 h soak with no unexplained reboots, Wi-Fi client and throughput tests, more LED states,
   idle CPU and RAM baseline, find out why the load average is ~3 on an idle CPU. Compare temperatures with the
   baseline in [THERMAL](THERMAL.md).
2. **Recovery slot.** Design the small kernel and rescue environment, how it is entered (boot record, button or
   failed boots), how it installs A, and the way back to stock. Prove it on the test unit with the download agent as
   the safety net, then retire the stock copy in B. Risk: today the fall-back to stock B is the safety net, so the
   recovery slot has to be as good before the stock copy goes.
3. **`sysupgrade`** for the new layout (A/B NAND with UBI and a preloader that picks the slot).
4. **Publish.** A stable tagged release, build documentation for other owners, and a device page for the OpenWrt
   wiki. The vendor modem blobs cannot be redistributed, so this ships the tooling and packages, not a ready image.
5. **Later.** Fan control from LuCI ([#47](https://github.com/mralinp/zlt-x28-openwrt/issues/47)), SMS and voice on the
   native image, and an own 4.19 kernel and kmod feed from a sibling-device SDK
   ([#130](https://github.com/mralinp/zlt-x28-openwrt/issues/130); not tried yet).

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Brick from a bad flash | high | Phase 0 dumps, UART, A/B slots, flash only the inactive slot |
| Signed rootfs / secure boot blocks custom images | low *(updated)* | Preloader reports SBC/SLA/DAA off, no rootfs content check was found, and the native image boots |
| `misc` (boot record) cannot be rewritten over USB | medium | The download-agent block write was never acknowledged; `misc` is changed live with the stock `dd-nand` method, never by an unattended tool |
| Boot counter runs out and stock B repairs (erases) slot A | high | `x28-bootok` resets the tries after every good boot; slot A stays unconfirmed so the fall-back exists |
| Modem and WiFi blobs tied to the 4.19 kernel | high | Stay on the vendor kernel; do not rebase to a newer kernel |
| No GPL source from the vendor | medium | Start from the stock rootfs and our own userland build; request source anyway |
| Heat from the 5G modem itself | low *(updated)* | About 40 °C idle on the native image; keep measuring under load |
| VoLTE needs operator provisioning | medium | Treat voice as separate: CS fallback, other SIM, or external gateway |
| Unknown reboot causes | medium | Reboot logger first; one change at a time; no multi-file deploys without a rollback |

## Operating rules (learned the hard way)

- Upload files with `COPYFILE_DISABLE=1 tar --uid 0 --gid 0` (macOS tar leaves `._*` files and wrong owners).
- One change per step, with the previous state backed up and checked non-empty.
- No password entry, session forging, or broad `find -exec` on the router.
- Do not run vendor binaries with unknown flags (`sms_mgr -h` rebooted the device).
- Keep `scripts/install.sh` and this repo as the reproducible record of every change.
