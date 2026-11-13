# Experimental IPv4 passthrough

This is a **timed, manual data-path experiment**, not a supported bridge-mode switch.
It is not installed in firmware, enabled at boot, or exposed in LuCI. The X28's
cellular `ccmni` interface carries raw IP, so it cannot simply join `br-lan`.

The helper temporarily routes the cellular IPv4 address to one existing LAN
peer, removes its local-delivery route on the X28, and exempts that source from
X28 masquerading. It keeps the LAN management address, normal NAT for other
clients, and existing WAN forwarding restrictions. A source-MAC guard rejects
other LAN clients claiming the passed-through address. This is an accidental
misconfiguration guard, not protection against MAC spoofing by a hostile LAN.

## Limits

- One IPv4 address, one existing `br-lan` peer, and an active `x28_mipc` WAN.
- Manual downstream `/32` address and source routing; **no DHCP handoff**.
- The test expires after 300 seconds by default (allowed: 10–600 seconds).
- X28-originated connections using the cellular IPv4 address may fail while
  the experiment is active: return packets are routed to the downstream peer.
  Do not run firmware/package updates during the experiment.
- IPv6 is untouched; test explicitly with IPv4. No IPv6 passthrough claim.
- Existing WAN firewall restrictions stay in place; this does not expose all
  incoming connections to the downstream router as some stock bridge modes do.
- The loop stops on address loss, changed return routing or a missing NAT
  exemption. It does not migrate the experiment to a new bearer.
- Normal exit, timeout, HUP, INT and TERM run cleanup. SIGKILL, a frozen process
  or a kernel failure cannot run shell traps. Keep the manual recovery below.

## Run on a recoverable lab setup

Use a downstream router with separate management access. Keep its existing
private WAN address/lease so the X28 can route the cellular address to that peer.
Record the original routing/firewall state on both devices first.

Copy `x28-passthrough` to `/tmp` on the X28 and run it in a dedicated SSH session:

```sh
# Example LAN peer; replace with your downstream router's existing WAN address.
ping -c 1 192.168.70.117
sh /tmp/x28-passthrough 192.168.70.117 300
```

The helper prints the current cellular IPv4 address. On the downstream router,
substitute it for `CELL_IP` below. Confirm table/rule 5300 is unused before adding
anything. These commands are temporary; do not commit them to UCI.

```sh
CELL_IP=198.51.100.10  # EXAMPLE ONLY: replace with the address the helper printed
ip addr add "$CELL_IP/32" dev wan
ip route add table 5300 192.168.70.0/24 dev wan
ip route add table 5300 default via 192.168.70.1 dev wan
ip rule add pref 5300 from "$CELL_IP/32" table 5300
```

On an OpenWrt fw4 downstream router, also insert a source-specific return before
its WAN masquerade rule and record the assigned handle:

```sh
nft insert rule inet fw4 srcnat_wan ip saddr "$CELL_IP" counter return comment '"x28-lab"'
nft -a list chain inet fw4 srcnat_wan
```

This example tests traffic originating on the downstream router. Its ordinary
LAN clients still use its existing NAT policy; do not describe their traffic as
using the alias without configuring and verifying that separately.

Run ping and the same IPv4 download endpoint, bound to the private WAN address
for the NAT baseline and to `CELL_IP` for passthrough. Bypass transparent proxies
**only for the benchmark destination**, and pin a real server address if DNS
uses fake IPs. In the live test, binding curl to `wan` alone did not bypass
Passwall2. Check both routers' NAT exemption counters and the client source IP.
Do not infer maximum 5G speed from a short single-connection HTTP download.

## Stop and recover

Ctrl-C the X28 helper or wait for expiry. Remove only the downstream state you
added; replace `HANDLE` with the handle recorded above:

```sh
ip rule del pref 5300 from "$CELL_IP/32" table 5300
ip route del table 5300 default via 192.168.70.1 dev wan
ip route del table 5300 192.168.70.0/24 dev wan
ip addr del "$CELL_IP/32" dev wan
nft delete rule inet fw4 srcnat_wan handle HANDLE
```

Verify private management access and internet access on both devices. If the
helper was killed without cleanup, restart the X28 WAN and reload its firewall
from the local management connection; remove the temporary host route if still
present. Remove the lock directory only after confirming no helper is running:

```sh
ifdown wan
ifup wan
/etc/init.d/firewall reload
# Substitute the old values recorded before the test, only if this route remains:
# ip route del OLD_CELL_IP/32 via LAN_PEER dev br-lan proto 186
rmdir /var/run/x28-passthrough
```

## Live evidence — 2026-11-11

X28, vendor kernel 4.19.205, native `x28_mipc`, raw-IP `ccmni1`; downstream
Linksys MX5300 running OpenWrt. The Linksys had an alternate preferred uplink and
Passwall2, so the accepted measurements used explicit source routing, a pinned
Cloudflare server and a destination-specific proxy bypass. No persistent network
configuration was changed. Both routers were restored and the X28 could ping
1.1.1.1 afterward.

| Mode | Three 20 MB HTTPS downloads (Mbps) |
|---|---|
| NAT, direct path | 76.7, 76.4, 61.5 |
| Temporary passthrough prototype | 79.3, 64.3, 73.9 |
| Guarded helper, subsequent run | 60.4, 65.7, 61.1 |

These sequential cellular measurements **do not establish a speed improvement**.
An earlier 50 MB passthrough run completed two downloads but its third stalled
and timed out; the cause is unresolved. Three smaller downloads and three more
with this exact helper completed. This is not a stability/throughput certification.
Ping, source-address handoff, NAT exemptions, signal cleanup, natural ten-second
timeout and ordinary NAT restoration were checked live. Partial setup failure,
termination, timed rollback and WAN address change are covered by `python3 tests/test_passthrough.py` with fake
network commands. No forced live modem reset, reboot, upload benchmark, DHCP
handoff or long soak was performed.
