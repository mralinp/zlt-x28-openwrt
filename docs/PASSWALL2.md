# Passwall2 on the native image

Issue: [#198](https://github.com/mralinp/zlt-x28-openwrt/issues/198). Tested on one unit, 2026-11-01 and 2026-11-02.

**Status: works on the unit for the whole LAN.** With TPROXY and socket modules we build for the vendor kernel,
Passwall2 starts with no warnings and carries the router's own traffic and LAN clients' TCP, UDP and IPv6 through the
node, switched on from LuCI ([TESTING 39](TESTING.md#39-tproxy-and-passwall2-on-the-unit-2026-11-02)). The image
build now ships Passwall2, xray and the modules; that image has not been flashed yet. Installed by hand on the unit, they
came back on their own after a reboot.

## How it fits this kernel

| Need | How it's met |
|---|---|
| `TPROXY` and `xt_socket` (not in the vendor kernel) | `nf_socket_ipv4/6`, `nf_tproxy_ipv4/6`, `xt_socket`, `xt_TPROXY` built from the SDK tree without symbol versions, like WireGuard ([#227](https://github.com/mralinp/zlt-x28-openwrt/issues/227)); `x28_udp_lookup` supplies `udp4_lib_lookup` and `udp6_lib_lookup`, which the stock kernel never exported. Why this loads despite the CRCs: [kernel-module-crc](research/kernel-module-crc.md) |
| Loading them safely | They live in `/lib/modules/x28`, not `/lib/modules/4.19.205`: there the kernel's `modprobe` would load them by itself for the first TPROXY rule, before the boot tries are reset and past the crash marker. `x28-kmods` (`package/x28-kmods`, S97) loads them after `x28-bootok` resets the boot tries, with a crash marker so a bad load can't become a boot loop, then starts Passwall2 if it is enabled, in case Passwall2's own delayed boot start ran before `xt_TPROXY` was in. Passwall2 keeps its boot link: LuCI's apply only restarts enabled services |
| No nftables | Passwall2's iptables path; the image sets `prefer_nft=0` and `tcp_proxy_way=tproxy` |
| ipset in `dnsmasq` | Our `dnsmasq-full` has `ipset no-nftset` (#203), and the vendor `ip_set` modules are in the image |
| `opkg` dependencies | `kmod-ipt-tproxy` and `kmod-ipt-socket` records at the kernel's version, so `iptables-mod-tproxy` and `-socket` resolve. `iptables-mod-extra` still wants `kmod-ipt-extra`, which has no stub yet |

The modules are built from the private SDK tree, so they never enter Git, CI or a feed. Build them as in
[TESTING 39](TESTING.md#39-tproxy-and-passwall2-on-the-unit-2026-11-02), strip debug info and pass the directory to
`first_boot.py --tproxy-modules` ([BUILD](BUILD.md#vpn-set-and-wireguard-in-the-image-230)).

Passwall2's `localhost_proxy` sends the router's own traffic through the node, including `opkg` and NTP. Behind a router
that already tunnels to the same node, `client_proxy` would tunnel that router's traffic twice; use Passwall2's access
control to pick clients instead.

## State of the test unit

Installed by hand the way the image will have it, not yet from an image:

- The 7 modules and WireGuard in `/lib/modules/x28`, where the kernel's `modprobe` can't load them on demand, loaded by
  `x28-kmods` (S97), which replaced `x28-wireguard`. Not yet rebooted from that directory. `ucitrack` (S80) started and enabled, so LuCI's Save & Apply restarts Passwall2 (its `reload` is a restart).
- `iptables-mod-tproxy`, `-socket` and `-extra` installed with `--nodeps`; `-iprange`, `-conntrack-extra` and the
  `kmod-ipt-nat` stub installed normally. No `kmod-ipt-tproxy`/`-socket` records yet.
- `/etc/config/passwall2`: `enabled=1`, `client_proxy=1`, `localhost_proxy=1`, `tcp_proxy_way=tproxy`, `ipv6_tproxy=1`,
  `prefer_nft=0`, node the owner's UK node (VLESS over XHTTP with TLS, an IPv6 literal, so it needs the WAN's IPv6, #50).
- LuCI over HTTPS with a self-signed certificate (`px5g-mbedtls`, `redirect_https=1`).
- Backups in `/root/backup-lan` (configs and the old loader), `/root/backup-tpx` and `/root/backup-198`.

To turn it off: the switch in LuCI, or `ssh x28 'uci set passwall2.@global[0].enabled=0; uci commit passwall2;
/etc/init.d/passwall2 stop'`. To remove the modules from boot: `ssh x28 '/etc/init.d/x28-kmods disable'` (this also drops
WireGuard, which `x28-kmods` loads too).

## Tunnel speed results

Method: a separate xray in `/tmp` using the node's generated config, with a SOCKS port on `127.0.0.1`. No firewall or
Passwall2 change. `curl` ran on the router and its CPU use is included. Single runs of 15 s or less, over cellular, so
treat these as rough.

| Test | Speed | Total CPU (4 cores) | xray |
|---|---|---|---|
| Direct download, 1 stream | 169.2 Mbit/s | 16.4% | n/a |
| Direct upload, 1 stream | 32.3 Mbit/s | 7.4% | n/a |
| Tunnel download, 1 stream | 126.1 Mbit/s | 35.5% | 0.66 core |
| Tunnel download, 4 streams | 66.9 Mbit/s | 18.2% | 0.33 core |
| Tunnel upload, 1 stream | 14.2 Mbit/s | 6.9% | 0.10 core |
| Direct download, 8 streams (6 worked) | 133.9 Mbit/s | 14.4% | n/a |
| Tunnel download, 8 streams (6 worked) | 162.4 Mbit/s | 43.2% | 0.82 core |

An earlier run measured 30.9 and 42.7 Mbit/s tunnel download, but the server was misconfigured at the time, so those
figures are left out.

In the 8-stream tunnel run the cores were 49.3%, 42.4%, 41.3% and 40.0% busy, with `cpu0` softirq at 19.2%. Temperature
was 42.8 °C on `thermal_zone0`, and xray's peak memory was 39 MB. Two of the 8 streams failed because
`speedtest.tele2.net` was unreachable.

The tunnel beating direct on the same servers means the test servers were limiting, so 162 Mbit/s is not the tunnel's
top speed.

**Context:** the owner reports over 300 Mbit/s on a speed test site through the same UK server on a Linksys MX5300,
whose gateway is this X28. So the WAN carries that speed. The Linksys figure was not measured here.

### Estimated top speed

These are estimates, not measurements. At 100% CPU: **300–450 Mbit/s, most likely around 400**. For everyday use, plan
on about 300 Mbit/s, or about 75% load.

- The whole router used 1.73 cores at 162 Mbit/s, which scales to about 375 Mbit/s on 4 cores. This assumes LAN
  forwarding costs about what the `curl` processes did.
- The CPU mostly ran around 1.3 GHz and can reach 2.0 GHz, which could raise the limit.
- Scaling losses, Wi-Fi, sustained heat with no fan, or `cpu0` filling up first could lower it.

### Reproduce

Uses mobile data: up to 400 MB per 8-stream run.

```sh
ssh x28
umask 077
lua /usr/lib/lua/luci/passwall2/util_xray.lua gen_config \
  '{"flag":"bench","node":"<node id>","local_socks_address":"127.0.0.1","local_socks_port":"10899"}' > /tmp/x28-bench.json
xray run -c /tmp/x28-bench.json >/dev/null 2>&1 &
curl -s -m 15 -o /dev/null -w '%{speed_download}\n' --socks5-hostname 127.0.0.1:10899 http://cachefly.cachefly.net/100mb.test
kill %1; rm -f /tmp/x28-bench.json
```

The generated config holds the node's credentials, so delete it afterwards. For several streams, start the `curl`
line in the background once per stream. For CPU, compare `/proc/stat` before and after.

## Not proven

- Throughput and CPU through the LAN path; the estimate above is for the router's own traffic.
- The modules over hours, and the image that ships them.
- Any tunnel speed above 162 Mbit/s, and sustained heat under load.
