# Project status — 2026-11-07

The older status snapshot (stock-firmware overlay era, 2026-10-21) is kept in
[archive/2026-10-21-STATUS.md](archive/2026-10-21-STATUS.md). Evidence for everything below is in
[TESTING.md](TESTING.md); what changed and when is in [../CHANGELOG.md](../CHANGELOG.md).

## Objective

A real OpenWrt on the ZLT X28: stock LuCI and UCI, netifd, standard DHCP/DNS and a kernel-compatible firewall own
networking; the vendor modem stack runs only as the hardware backend. No copy of the vendor web UI, no UCI-to-vendor
adapter. Preserve the working modem, board calibration and recoverability.

## Where it stands

Release `v0.57.2`. The native image (OpenWrt 23.05.5 userspace on the vendor 4.19.205 kernel, fw3 + iptables-legacy)
is flashed to slot A of one test unit and boots; stock slot B is untouched.

**Working on that unit**
- 5G data through the `x28_mipc` netifd protocol (IPv4, IPv6, IPv4v6, APN from the SIM) and its LuCI page.
- LuCI over HTTPS (self-signed certificate made on first boot, HTTP redirected), a four-socket LAN bridge, `dnsmasq` DHCP and DNS, IPv6 on the LAN, firewall and NAT.
- Wi-Fi on the MT7915 dual band through the vendor `mt_wifi` driver (both radios up, WPA2).
- Front panel LEDs from radio, signal and WAN state.
- The modem stack, services and Wi-Fi defaults start at boot; settings, host keys and the root password survive reboots.
- SSH takes the owner's key or the root password on port 22 (LAN only). Root has an empty password until the owner sets one (LuCI or `passwd`), like stock OpenWrt; dropbear never accepts an empty password, so password login starts then.
- The A/B boot counter is reset after every good boot (`x28-bootok`), as stock does.
- About 40 °C idle on the SoC; the CPU is almost fully idle.
- `opkg` works through our signed feed on a stable URL ([PACKAGE-FEED](PACKAGE-FEED.md)): 205 of the 976 official `kmod-*`
  packages install (180 stubs and 25 built for this kernel), the rest are refused ([TESTING 42](TESTING.md)). OpenVPN, L2TP, PPTP and WireGuard clients are available; WireGuard uses a module
  built for this kernel with no symbol version check, loaded late at boot ([BUILD](BUILD.md), [TESTING 37](TESTING.md)).
- Passwall2 runs on TPROXY and socket modules built the same way: the router's own traffic and LAN clients' TCP, UDP and
  IPv6 go through the node with no warnings, switched from LuCI, and it comes back after a reboot ([PASSWALL2](PASSWALL2.md)).
  Every image build ships it.
- LuCI Carrier tab on the `x28_mipc` protocol: operator (automatic or manual, with a network scan), 4G and 5G band lock, cell lock, roaming (default off) and modem status (v0.54 – v0.57).
- WPS push button, one Wi-Fi network per band (v0.38.6 – v0.39.1).
- The flasher, backup and image assembly moved to [mralinp/x28-flasher](https://github.com/mralinp/x28-flasher), which is private for now; releases here publish the `x28-assembly` bundle it consumes (the `x28-overlay` asset until v0.57).

**Open or unproven**
- Slot A is not marked successful (success byte 0). Deliberate: it keeps the preloader's fall-back to stock B.
  Stock marks success together with copying A over B, which this image never does ([BOOT-FLOW](BOOT-FLOW.md)).
- The download-agent block write to `misc` was never acknowledged (twice). `misc` is changed live with the stock
  `dd-nand` method instead; there is no proven off-device way to rewrite `misc`.
- Wi-Fi client and throughput tests and more LED states are pending. A 26.6 h soak showed no unexplained restart, but
  available memory falls ([#213](https://github.com/mralinp/zlt-x28-openwrt/issues/213)). The load average of about 3 is
  vendor threads in uninterruptible sleep, harmless ([TESTING 33](TESTING.md)).
- SMS and voice worked on the stock-firmware overlay (voice blocked by the SIM) and are not ported to the native image.
- One unit, one SIM, one carrier. Hardware revision differences are unknown.

## Known limits of the base

- The vendor modem userspace is closed and not redistributable, so no ready-to-flash image can be published; the build
  copies it from the owner's own backup.
- The vendor 4.19.205 kernel has no `nf_tables` (so fw3), no namespaces (so no `ujail`), and `CONFIG_MODVERSIONS`: the
  official feeds' kernel modules do not load, userspace packages do. `opkg` works through our signed
  [feed](PACKAGE-FEED.md): stubs for what the kernel has, built modules for what it lacks and can take, and a clear refusal for the
  rest ([TESTING 36](TESTING.md), [TESTING 42](TESTING.md)).

## Next

See the roadmap in [PROJECT-PLAN.md](PROJECT-PLAN.md): test slot A, then a recovery slot on B (a small kernel
and rescue path that installs OpenWrt on A and can restore stock), `sysupgrade` for that layout, a stable release and
the OpenWrt wiki device page; later fan control, SMS/voice on the native image and an own 4.19 kernel built from a
sibling-device SDK ([#130](https://github.com/mralinp/zlt-x28-openwrt/issues/130)).
