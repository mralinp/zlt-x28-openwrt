# X28 native OpenWrt cellular: the `x28_mipc` protocol

Shipped in the native image since `v0.20.0` and validated on a real X28 (slot A, 2026-10-29): IPv4, IPv6 and IPv4v6, the
APN read from the SIM when none is set, started at boot by `x28-modem`. The protocol appears in LuCI under
Network > Interfaces like any other. Hardware validation notes are at the end; open items are listed under Limits.

This is the first native cellular integration slice for the ZLT X28. Stock LuCI uses a normal protocol extension, UCI supplies configuration, and netifd receives the bearer device, IPv4 address, default route, DNS and lifecycle notifications. There is no OEM CGI bridge or replacement of the core Interfaces page.

## Contents

- `package/x28-mipc`: native netifd protocol `x28_mipc` and the `x28-apn` helper (APN from the SIM, using the stock `/etc/conf/apns-conf_8.xml` database).
- `package/luci-proto-x28-mipc`: ordinary LuCI protocol extension.
- `package/x28-modem`: boot script that starts the vendor modem stack, the USB gadget `atcid` needs, the radio and `ifup wan`.
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

One native cellular WAN, no PAP/CHAP, no SIM PIN submission. The external CLI has no explicit timeout; hangs and netifd
cancellation need a long-run test. Reconnect after a modem reset or link loss has been seen to re-bind the firewall NAT
but has not been soak-tested on the final image. `mtk_netagent` is deliberately not started: it forces the radio off
(`CFUN 0/4`); IPv6 is handled by the protocol instead (it keeps the modem's link-local address and lets the kernel autoconfigure from the router advertisement).
Existing OEM LuCI wrappers are excluded from this port.

Next: more SIMs and operators, PIN and PAP/CHAP, and a long reconnect soak ([TASKS](TASKS.md) section D).

## Hardware validation, 2026-10-29 (slot A, first run on the X28)

The protocol ran on a real X28 booted from slot A with the native 23.05.5 userland, the modem stack started by hand
(`nvram_daemon`, `ccci_fsd 0 2 0`, `ccci_mdinit 0`, `ql_ril_service`, `ql_netd`, `mipc_submonitor`, `atci_service`,
`atcid` with a one-serial-port USB gadget), the radio on (`AT+CFUN=1`) and the SIM ready. `network.wan` was
`proto x28_mipc`, `apn internet`, `iptype 1`.

- **Bug found and fixed:** the kernel leaves `ccmniN` DOWN after `--data_call_act`, so the `LINK_NOT_READY` check always
  failed and the protocol looped (activate, fail, deactivate, retry). The protocol now brings the validated `ccmniN`
  device up first. The 31 mocked lifecycle cases still pass.
- **Result:** `wan` came up in about 3 seconds on `ccmni1` with an IPv4 address, a default route and the operator's DNS;
  pings to `1.1.1.1` and `8.8.8.8` had 0% loss and DNS plus an HTTP fetch worked from the router.
- **Not started:** `mtk_netagent` forces `AT+CFUN=0`/`4` when started in this order and was left stopped; its role (IPv6 RA
  on the `ccmni` devices, modem-reset handling) and the correct start order are still open.
- **Not verified:** IPv6, reconnect after modem reset or link loss, LAN clients (NAT/firewall), reboot persistence of
  the whole stack, and throughput.

### Final image, 2026-10-29 (`v0.22.0`)

The same protocol started by `x28-modem` at boot, with no manual step: after each boot `wan` came up on `ccmni1` with an
IPv4 address and a default route, pings and DNS worked, NAT was bound to `ccmni1`, and this survived reboots. The first
boot of the previous image looped on `NO_SIM_APN` because the APN database `/etc/conf/apns-conf_8.xml` was missing from
the image; it is now copied from the stock rootfs (`v0.21.2`). Still unverified: a long reconnect soak, throughput, and
other operators or SIMs.

## License

Original package sources and tests: GPL-2.0-only. See https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt . No vendor executables, firmware, credentials, calibration or private backups are included.
