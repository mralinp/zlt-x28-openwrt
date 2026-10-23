# X28 native OpenWrt cellular prototype

Version 0.1.0 — source only; not a flashable image or a hardware-validated WAN replacement.

This is the first native cellular integration slice for the ZLT X28. Stock LuCI uses a normal protocol extension, UCI supplies configuration, and netifd receives the bearer device, IPv4 address, default route, DNS and lifecycle notifications. There is no OEM CGI bridge or replacement of the core Interfaces page.

## Contents

- `package/x28-mipc`: native netifd protocol `x28_mipc`.
- `package/luci-proto-x28-mipc`: ordinary LuCI protocol extension.
- `tests`: mocked lifecycle tests and local LuCI registration/validation checks.
- `examples/network.disabled`: deliberately disabled configuration example.

## Hardware boundary

Requires a pre-initialized modem, its CCCI/kernel support, and an ABI-compatible `mipc_wan_cli` supplied separately by the vendor `mipc-wan` package. These dependencies are not included. The existing vendor package's source, licensing, libraries and startup side effects still need auditing before a clean firmware build. Retaining a hardware dependency does not make vendor LAN/WAN policy managers part of the target design.

The handler refuses setup while `wan_mgr` is running. It serializes its own operations, validates configuration and modem replies, reports a dynamic ccmni device, and records the CID with an interface ownership marker. Cleanup deactivates only that returned CID; it never deactivates by APN, kills processes or edits DHCP/firewall configuration. The marker records protocol ownership; it cannot prove the modem allocated a new bearer. That modem behavior must be verified on recoverable hardware.

## Build integration

Copy the two package directories into an appropriate OpenWrt build tree and select both packages. The tree must provide `mipc-wan`, netifd, jshn, flock and LuCI. Review compatibility against the chosen release; an IPK build has not been run. Current upstream kernel compatibility is not established. No init script, automatic activation or network config is installed by these packages.

Do not enable this protocol on the active vendor-managed gateway. Use a spare unit with proven UART/USB restore and fallback internet for ownership migration.

## Checks performed, 2026-10-21

- 31 mocked lifecycle cases passed using the router's installed OpenWrt JSON and netifd shell helpers.
- Modem, ubus, link queries and vendor-process checks were mocked; no live modem activation, deactivation or network notification was issued.
- Test artifacts were staged in a unique /tmp directory and removed afterward. Installed handlers were not changed.
- Local LuCI protocol registration, runtime device selection, input validation and routing/DNS fields passed.
- Shell syntax checks passed.

Run local checks with `node tests/test_luci.cjs` and `sh -n package/x28-mipc/files/x28_mipc.sh tests/run-case.sh`.
Run mock helper tests with `python3 tests/test_native.py --router router`. This needs SSH/SCP and the device's existing OpenWrt helpers. Read the harness before running it on another system.

## Limits and next work

IPv4 only, one native cellular WAN, no PAP/CHAP, SIM PIN submission, modem cold-start, IPv6 or proven reconnect behavior. The external CLI has no explicit timeout in this prototype; hangs and netifd cancellation still need hardware validation. No kernel, image, boot, real routing, MTU application, firewall, Wi-Fi or throughput tests have passed for this prototype.

Next: trace minimal modem boot dependencies, establish recovery, measure switch topology, build a clean wired rootfs, then validate modem lifecycle and native wireless integration. Existing OEM LuCI wrappers are excluded from this port.

## License

Original package sources and tests: GPL-2.0-only. See https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt . No vendor executables, firmware, credentials, calibration or private backups are included.
