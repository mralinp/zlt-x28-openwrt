# Project status — 2026-10-29

The older status snapshot (stock-firmware overlay era, 2026-10-21) is kept in
[archive/2026-10-21-STATUS.md](archive/2026-10-21-STATUS.md). Evidence for everything below is in
[TESTING.md](TESTING.md); what changed and when is in [../CHANGELOG.md](../CHANGELOG.md).

## Objective

A real OpenWrt on the ZLT X28: stock LuCI and UCI, netifd, standard DHCP/DNS and a kernel-compatible firewall own
networking; the vendor modem stack runs only as the hardware backend. No copy of the vendor web UI, no UCI-to-vendor
adapter. Preserve the working modem, board calibration and recoverability.

## Where it stands

Release `v0.22.0`. The native image (OpenWrt 23.05.5 userspace on the vendor 4.19.205 kernel, fw3 + iptables-legacy)
is flashed to slot A of one test unit and boots; stock slot B is untouched.

**Working on that unit**
- 5G data through the `x28_mipc` netifd protocol (IPv4, IPv6, IPv4v6, APN from the SIM) and its LuCI page.
- LuCI, a four-socket LAN bridge, `dnsmasq` DHCP and DNS, IPv6 on the LAN, firewall and NAT.
- Wi-Fi on the MT7915 dual band through the vendor `mt_wifi` driver (both radios up, WPA2).
- Front panel LEDs from radio, signal and WAN state.
- The modem stack, services and Wi-Fi defaults start at boot; settings, host keys and the root password survive reboots.
- SSH is key-only on port 22 (LAN only); root has an empty password until the owner sets one, like stock OpenWrt.
- The A/B boot counter is reset after every good boot (`x28-bootok`), as stock does.
- About 40 °C idle on the SoC; the CPU is almost fully idle.

**Open or unproven**
- Slot A is not marked successful (success byte 0). Deliberate: it keeps the preloader's fall-back to stock B.
  Stock marks success together with copying A over B, which this image never does ([BOOT-FLOW](BOOT-FLOW.md)).
- The download-agent block write to `misc` was never acknowledged (twice). `misc` is changed live with the stock
  `dd-nand` method instead; there is no proven off-device way to rewrite `misc`.
- Wi-Fi client and throughput tests, more LED states, and a long soak are pending. The load average sits around 3 with
  an idle CPU (probably vendor driver threads in uninterruptible sleep); not yet explained.
- SMS and voice worked on the stock-firmware overlay (voice blocked by the SIM) and are not ported to the native image.
- One unit, one SIM, one carrier. Hardware revision differences are unknown.

## Known limits of the base

- The vendor modem userspace is closed and not redistributable, so no ready-to-flash image can be published; the build
  copies it from the owner's own backup.
- The vendor 4.19.205 kernel has no `nf_tables` (so fw3), no namespaces (so no `ujail`), and `CONFIG_MODVERSIONS`: the
  official feeds' kernel modules do not load, userspace packages do.

## Next

See the roadmap in [PROJECT-PLAN.md](PROJECT-PLAN.md): soak and test slot A, then a recovery slot on B (a small kernel
and rescue path that installs OpenWrt on A and can restore stock), `sysupgrade` for that layout, a stable release and
the OpenWrt wiki device page; later fan control, SMS/voice on the native image and an own 4.19 kernel built from a
sibling-device SDK ([#130](https://github.com/mralinp/zlt-x28-openwrt/issues/130)).
