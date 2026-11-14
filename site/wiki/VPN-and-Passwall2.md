# VPN and Passwall2

Every image ships WireGuard, OpenVPN, `dnsmasq-full` with ipset, and Passwall2 with `xray`. L2TP and PPTP clients install from
the feeds but were not tested against a server.

## Measured speed

| Tunnel | Result | Limit |
|---|---|---|
| WireGuard | 715 Mbit/s sending, 330 receiving | CPU not saturated (under 60 %); runs in the kernel on all four cores |
| OpenVPN | about 100 Mbit/s | one core |
| Passwall2 (xray, VLESS over XHTTP with TLS) | 206 Mbit/s down, 40 up from a LAN client | the link ran out first; router CPU peaked at 56 % |

xray costs about **0.45 cores per 100 Mbit/s**. Estimated ceiling 300 to 450 Mbit/s; plan on about 300. The ceiling was not
reached in a measurement.

## WireGuard

`kmod-wireguard` is a module built for this kernel, loaded late at boot by `x28-kmods`. Configure it in LuCI as on any OpenWrt.

## Passwall2

It needs TPROXY and socket matching, which the vendor kernel lacks. We build seven modules for it (`nf_tproxy_ipv4/6`,
`nf_socket_ipv4/6`, `xt_TPROXY`, `xt_socket`, and `x28_udp_lookup`, which supplies two functions the stock kernel never exported).
The image sets Passwall2 to its iptables path (`prefer_nft=0`, `tcp_proxy_way=tproxy`).

### Turning it on

It ships **off**, with no node.

1. Add your node (Node List), then set **Node** in Basic Settings to it. The default `rulenode` points at a placeholder.
2. Avoid shunt rules that need a `geosite` entry missing from the image's `geosite.dat` (for example `IR`). xray refuses to start,
   the firewall rules still load, and **the LAN goes offline** until you stop the service. The stock `CN` group is fine.
3. For IPv6 on LAN clients, tick IPv6 TProxy (Other Settings > Forwarding Settings). While Passwall2 is on, the kill switch
   rejects direct IPv6.
4. If the LAN goes dark: `ssh x28 '/etc/init.d/passwall2 stop'`.

### LAN kill switch

While Passwall2 is enabled in UCI, direct forwarded cellular traffic is rejected (IPv4 and IPv6). Exempt: ICMP, the node itself,
and destinations Passwall2 sends direct. Router-originated traffic is outside it. It is not a full privacy guarantee.

- Turning Passwall2 off in LuCI removes the guard.
- Stopping the service without turning it off in UCI keeps the guard.
- To clear it by hand after disabling: `/etc/x28-killswitch.sh`.
- A Passwall2 package upgrade can replace the init hooks; recheck after one.

### Do not torrent through it

Each tracker, DHT and peer UDP flow becomes an xray session held for 300 s. One client left xray with 3,597 sockets and 288 MB in
30 minutes; LuCI and SSH hung. `/etc/init.d/passwall2 restart` recovers. This is upstream behaviour on a 640 MB router.

### Going faster

Tried: more parallel streams. Untested ideas: a lighter transport (plain VLESS or REALITY), node log at `warn`,
`packet_steering=1` (all Ethernet interrupts land on `cpu0`), the `performance` governor, a fan.

### Upgrades through Passwall2

`x28-upgrade` downloads firmware with `curl`, because `uclient-fetch` timed out through the proxy (#524).

Full document: [PASSWALL2](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/PASSWALL2.md), tests 37 and 39 to 41 in
[TESTING](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/TESTING.md).
