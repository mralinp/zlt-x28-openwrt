# Native OpenWrt port: initial X28 audit

Read-only inspection on 2026-10-21, stock firmware 1.5.13. No network daemon was started, stopped or reconfigured during this audit. The scope is defined in [the corrected plan](PROJECT-PLAN.md).

## Observations

| Layer | Device evidence | Port implication |
| --- | --- | --- |
| Network manager | `/sbin/netifd` exists; installed package reports `2021-01-09-753c351b-1`. No netifd process was present in the sampled process list. | A native networking foundation exists, but installation alone does not mean it owns the live interfaces. |
| Interface RPC | `ubus list` showed `network` and `network.rrdns`; no `network.interface.*` objects in the sample. | A status-only page cannot substitute for real interface lifecycle and notifications. |
| Standard services | `/sbin/fw3`, `/usr/sbin/dnsmasq`, `/usr/sbin/odhcpd`, and network/firewall init scripts exist. `/etc/init.d/dnsmasq` was absent in the preceding inspection. | Restore complete upstream packages/init scripts in the clean rootfs rather than enabling isolated dormant binaries against stale configuration. |
| Runtime ownership | `lan_mgr`, `wan_mgr`, `mtk_netagent`, `mipc_submonitor` and `wapp` were active. | Identify which modem services are hardware dependencies and remove competing LAN/WAN policy ownership in the test image. |
| Cellular protocol | `mipc.sh` and `ql_mipc.sh` exist under `/lib/netifd/proto`; `mipc_wan_cli` exists. | There is a direct modem-to-netifd integration path to audit. No web API is needed in the target architecture. |
| Switch | `swconfig list` identifies `switch0 - MT7531AE`. | The switch is visible through a standard OpenWrt mechanism. Physical ports, CPU ports and VLAN membership remain unverified. |
| Wireless | `/sbin/wifi` is a Lua replacement using `mtkwifi`; `/lib/netifd/wireless` is absent. Hostapd/wpa_supplicant were not found at the inspected standard paths. | Proper wireless lifecycle integration or an upstream driver port is required. Renaming the current Wi-Fi page cannot provide it. |
| Runtime versus UCI | Earlier evidence showed live LAN `br0` at `192.168.70.1`, while UCI described a different LAN address; the live modem bearer also differed from stale UCI assumptions. | Do not start stock services against the current config. Build and test the native configuration separately. |

The root `network` ubus object was not attributed to a process during this audit. Its presence is not evidence of working native netifd interface objects.

## Cellular interface reference

Both installed protocol handlers declare UCI inputs, call `mipc_wan_cli`, parse its response and use native `proto_init_update`, address/route/DNS helpers and `proto_send_update`. The existing activation response parser references fields including:

```text
result, cid, ifname
v4_addr, v4_mask, v4_gw, v4_dns1, v4_dns2, v4_mtu
v6_addr, v6_prefix, v6_gw, v6_dns1, v6_dns2, v6_mtu
```

These names come from inspected scripts. No new bearer was activated to independently verify their values, prefix semantics or failure behavior. The assigned bearer device must be learned from the modem rather than fixed to one `ccmni` index.

The scripts are not ready for blind reuse:

- `mipc.sh` deactivates by APN before setup and globally kills `mipc_wan_cli` on teardown. That can affect bearers outside the interface being managed.
- Both include bridge-mode paths that restart or reconfigure dnsmasq. `ql_mipc.sh` can clear lease files in those paths.
- `mipc.sh` changes UCI firewall zones, DHCP RA configuration and CLAT configuration from the modem handler. Those policies belong to the relevant OpenWrt services.
- IPv6 prefix construction, registration/attach retries, modem readiness, ULA handling and failure cleanup need explicit tests. The scripts' existence does not establish correct dual-stack behavior.
- Local package metadata and repository descriptions are insufficient to establish redistribution rights for all modem libraries, binaries and kernel components.

The native handler should validate input and responses, manage only its own bearer, and report state to netifd. OpenWrt should own routing policy, DHCP and firewall changes through normal configuration and hotplug mechanisms. Upstream netifd defines a [protocol interface](https://lxr.openwrt.org/source/netifd/proto.h) and [wireless setup/teardown and notification helpers](https://lxr.openwrt.org/source/netifd/scripts/netifd-wireless.sh); the handler version must match the chosen build baseline.

## Ownership target

| Function | Target owner | Acceptance evidence |
| --- | --- | --- |
| LAN devices/bridge/address | netifd + UCI network | Standard per-interface ubus status, Save/Apply and reboot behavior match the actual hardware. |
| Cellular bearer | Native netifd protocol + required low-level modem interface | ifup/ifdown, failure and reconnect update real interface state without OEM CGI. |
| Wi-Fi | netifd wireless backend; upstream mt76/mac80211 where proven feasible | UCI wireless and ordinary LuCI drive the actual radios and network membership. |
| DHCP/DNS/RA | Upstream dnsmasq/odhcpd services | Standard config is authoritative; no vendor manager rewrites it. |
| Filtering/NAT | Kernel-compatible OpenWrt firewall service | Standard UCI firewall rules control packet behavior and preserve management access. |
| User interface | Upstream LuCI network modules | No vendor credential proxy or custom replacement of the core configuration pages. |

## Current blockers and next deliverables

The exact MT6890 kernel/SDK build inputs and proven recovery for this hardware remain missing. A full image has not been built or booted. The public X28 userspace-port repository is a reference for the dependency boundary, not proof that its build inputs or settings fit this router.

Next deliverables are a minimal modem boot dependency graph, measured Ethernet topology, chosen kernel/userspace/toolchain baseline and an audited native cellular handler with mocked lifecycle tests. A clean rootfs and recoverable wired-LAN test follow. The prior LuCI wrapper bundles are excluded from that rootfs; they are historical OEM UI work, not port milestones.
