# X28 LuCI network integration — 2026-10-21

**Scope:** This is historical OEM UI adaptation. It is excluded from the native OpenWrt firmware port. See [the corrected port plan](../x28-plan.md).

Follow-on integration installed: [vendor firewall and DHCP lease mapping](../x28-luci-firewall-integration/README.md). Port forwarding and DMZ now live under Firewall, and the lease-reader path matches the vendor service. Revert that follow-on stage before rolling back this earlier stage.

Installed on this ZLT X28, stock firmware 1.5.13. This is a LuCI compatibility layer over the vendor network services. It does not replace firmware or make those services implement standard OpenWrt netifd/ubus interfaces.

## Navigation and mapping

| Page | Configuration source / behavior |
| --- | --- |
| Network → Interfaces | Live kernel addresses, bridges, bridge membership and IPv4 default routes; links to the matching configuration page. |
| Network → Wireless | Existing vendor Wi-Fi controls, using CGI commands 2 and 211. No UCI wireless file is fabricated. |
| Network → LAN / DHCP | Existing vendor command 3 for DHCP range, lease time and DNS. LAN IP/netmask remain read-only, as before. |
| Network → WAN / Cellular | Command 133 reports the connection; command 248 reads and selects an existing APN profile; command 213/subcommand 3 controls IP protocol, MTU and NAT. |
| Network → Port forwarding / DMZ | Existing vendor controls moved into Network. |
| Services → SMS / USSD / Voice | Existing controls moved into Services. |

The separate Vendor and MTK menus are hidden. Old vendor page URLs resolve to their new destinations; existing vendor API URLs and MediaTek endpoints are retained. Stock UCI Hostnames and Static Routes entries are hidden because their settings do not describe the live vendor-managed network; their direct routes are retained.

Observed mapping on this device: `br0` is LAN at `192.168.70.1/24`; `ccmni1` carries the IPv4 default route and current `mcinet` APN; `ra0` and `rai0` are active Wi-Fi devices in `br0`. The runtime page derives the WAN from the kernel default route, rather than assuming `ccmni1` forever. Extra modem interfaces are shown without treating them as additional configurable internet connections.

## Verification

- New JavaScript logic tested with `node test-ui.cjs`, using mock responses: serialized requests and recovery after HTTP failure, live device mapping, preservation of unknown APN fields, default selection, IPv6 MTU validation, cancelled writes, rejected writes. No live settings were changed by these tests.
- Lua syntax and generated menu checked on the router; expected Network/Services entries are present and duplicate Vendor/MTK headings have no title.
- Live status handler checked against the current LAN bridge and default route.
- Interfaces page rendered in the browser with the correct live addresses and configuration links.
- `/etc/config` and `/etc/wireless` file hashes, and routes, were identical before and after deployment. Router internet ping passed with no loss. No network services restarted.
- Final browser checks passed: unified navigation, both Wi-Fi bands, live LAN/DHCP range and DNS, and WAN/Cellular APN, addresses, MTU and NAT. Normal LuCI login succeeded with the supplied credentials; passwords were not changed. Proof screenshot: `unified-network.png`.
- Parallel vendor reads caused an incomplete cellular page load during browser testing. Sequential reads succeeded; the shared vendor page helper now queues requests, with a mock test for serialization and queue recovery after failure.

## Limits and next work

Live write/apply operations were deliberately not exercised because they can reconnect the router providing internet. The cellular requests follow the device's own shipped UI source and were tested against mocks; vendor acknowledgement is not a connectivity or persistence check. There is no automatic rollback timer for vendor CGI changes. After a cellular apply, reload the page after reconnection and verify the reported state.

Existing LAN/Wi-Fi form validation and behavior are retained. Adding/editing APN definitions, editable LAN addresses, arbitrary interfaces, VLAN topology changes, stock firewall policy, DHCP leases on Overview, and VPN integration are not implemented by this patch. The stock Firewall page remains present and has not been validated against vendor rules. This patch alone does not make Passwall2 or netifd-dependent packages work.

The next compatibility work should map vendor firewall policy and lease data, then add a tested configuration transaction/rollback mechanism before exposing topology changes. Avoid running a second independent network manager against the same devices.

## Files and rollback

`files/` contains the deployed controller/view sources. `test-ui.cjs` runs locally using Node. `ui-files.tgz` contains the same source tree for this particular installed LuCI version; it is not a firmware image or a generic OpenWrt package.

The original three controllers are backed up on the router at `/root/x28-network-ui-backup-20261021/controllers.tgz`; the original shared JavaScript helper is `vendor-js.htm` in that directory. To restore navigation from this Mac, run from this directory:

```sh
ssh router 'sh -s' < rollback.sh
```

This restores the original controllers and shared helper, and clears only LuCI caches. Log out and back in afterward to refresh the browser's cached menu. The two unused new templates can remain safely on disk. Rollback does not undo any network settings a user later applies.
