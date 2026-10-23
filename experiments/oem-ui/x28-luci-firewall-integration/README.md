# X28 vendor firewall and DHCP lease integration

**Scope:** This is historical OEM UI adaptation. It is excluded from the native OpenWrt firmware port. See [the corrected port plan](../x28-plan.md).

Installed on 2026-10-21, following the Network menu integration on this ZLT X28 firmware 1.5.13. This is a LuCI adaptation for the existing vendor services, not replacement firmware or standard OpenWrt netifd support.

## Changes

- **Network → Firewall → General Settings** reads the vendor firewall flag, DoS/ACK flood protection, and the actual IPv4/IPv6 kernel filter and NAT rules.
- **Port Forwards** and **DMZ** tabs reuse the existing vendor controls. Duplicate top-level Network entries are replaced with aliases; old Network and Vendor URLs still resolve.
- The stock fw3 zones, traffic-rule, source-NAT and custom-rule editors are no longer exposed. Their old URLs resolve to the vendor firewall page. Their UCI zones do not match the running vendor-managed chains.
- The DoS protection control uses a dedicated authenticated, CSRF-protected POST action. It validates a boolean, reads the current state, skips identical values, uses only vendor command 275, and reads back the state after an acknowledged change. ACK flood state and the overall firewall flag are shown read-only.
- LuCI's UCI lease-reader path now matches the running vendor dnsmasq: `/tmp/dnsmasq.leases`. The DHCP process and live DHCP configuration were not restarted or rewritten. The stock lease RPC now returns the two IPv4 entries from the real file.

The vendor firewall flag API did not report a protection level. Rule-list APIs also did not report complete filter arrays. The UI does not invent values or submit replacement lists for those settings. Missing protection state disables its control until a successful refresh. A transient missing-field response was observed in a read-only verification; the next read and browser display returned the expected flags.

Kernel default policies are shown separately from actual blocking rules: an ACCEPT fallback does not mean traffic bypasses the vendor chains.

## Verification

- `node test-firewall-ui.cjs` passes: live-state rendering, missing data, no-op and cancelled writes, JSON/CSRF request construction, and disabled controls after an unsuccessful write.
- `test-firewall.lua` passes on the router against staged code with the vendor backend mocked: filter/NAT parsing, invalid input, command restriction, no-op writes, rejection and readback mismatch.
- The generated LuCI menu has the expected vendor-backed tabs and a POST-protected action. Duplicate Network entries have no menu title.
- Normal authenticated HTTP tests confirmed GET to the protection action returns **405**, and POST without a CSRF token returns **403**. The test body was deliberately invalid and could not change protection even if CSRF validation failed.
- Chrome verification passed for the live protection state, IPv4/IPv6 policies, forwarding and DMZ tabs, and both real IPv4 leases with hostnames, addresses and remaining lease times on Overview. Screenshot: `firewall.png`.
- Both IPv4 and IPv6 rule snapshots, with counters normalized, and the routing table were identical before and after deployment. No valid live protection change was submitted.

## Remaining limits

The existing forwarding/DMZ write behavior is reused; no forwarding or DMZ rule was added, changed or removed during verification. The new DoS write path was tested with a mock, not by toggling live protection. Applying those settings can briefly interrupt traffic, and vendor writes have no automatic rollback timer.

Arbitrary OpenWrt firewall zones and traffic rules still require a proper policy adapter and rollback mechanism. This patch does not make netifd-dependent VPN packages work. IPv6 lease reporting continues to use the existing LuCI RPC; an empty IPv6 table is not a statement that no IPv6 clients exist.

## Sources and rollback

`files/` and `ui-files.tgz` contain the deployed controller/view source for this particular LuCI installation. They are not a flashable image. The only UCI change is:

```sh
uci set dhcp.@dnsmasq[0].leasefile=/tmp/dnsmasq.leases
uci commit dhcp
```

Original files and normalized rule/route snapshots are on the router at `/root/x28-firewall-ui-backup-20261021/`. From this directory on the Mac:

```sh
ssh router 'sh -s' < rollback.sh
```

Rollback restores the previous two controllers and only the old DHCP lease-reader option, preserving other later DHCP UCI edits. It clears LuCI caches without restarting DHCP or firewall services. The unused new template can remain on disk. It does not revert later firewall changes applied by a user.

If reverting multiple integration stages, revert this firewall stage before the earlier Network menu stage.
