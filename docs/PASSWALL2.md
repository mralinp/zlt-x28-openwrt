# Passwall2 on the native image

Issue: [#198](https://github.com/mralinp/zlt-x28-openwrt/issues/198). Tested on one unit, 2026-11-01.

**Status: on hold until the kernel and package manager are fixed.** Passwall2 is installed and configured on the test
unit but disabled, and has never been enabled there. The tunnel itself works: xray reached 162 Mbit/s with CPU to spare.
Transparent proxying for LAN clients is untested.

## What blocks it

| Blocker | Evidence | Effect |
|---|---|---|
| No `TPROXY` or `xt_socket` in the vendor kernel | `CONFIG_NETFILTER_XT_TARGET_TPROXY`, `CONFIG_NF_TPROXY_*` and `CONFIG_NETFILTER_XT_MATCH_SOCKET` are not set | UDP can't be proxied transparently; TCP has to use `redirect` |
| No nftables in the vendor kernel | No `nf_tables`; the image uses fw3 and iptables-legacy | Passwall2 has to use its iptables path |
| Feed kmods don't match the kernel | Feed `kmod-*` packages need `kernel` 5.15.167; the unit runs 4.19.205 | Plain `opkg install` can't resolve kmod dependencies, so packages such as `ipset` need `--nodeps` |
| `dnsmasq` has no ipset support | `dnsmasq --version` lists `no-ipset no-nftset`; `dnsmasq --test` rejects an `ipset=` line with "recompile with HAVE_IPSET defined" | Passwall2 instances given an `ipset=` line can't start |
| Passwall2 misreads that `dnsmasq` | `app.sh` runs `grep -qw ipset`, which also matches `no-ipset`, and logs `dnsmasq_ipset:1` | No warning about the row above |

The 23.05.5 `dnsmasq-full` probably doesn't help: its published dependencies include `nftables-json` but not
`kmod-ipt-ipset`, which suggests it was built with nftset and without ipset. This comes from the package metadata; the
binary was not checked.

## When to come back to this

1. Build a 4.19 kernel module feed ([#130](https://github.com/mralinp/zlt-x28-openwrt/issues/130)) with `xt_TPROXY`,
   `xt_socket` and the matching `nf_tproxy` modules, and make `opkg` resolve kmod dependencies against it.
2. Build `dnsmasq-full` with ipset on and nftset off, in `tools/build/sdk_packages.sh`, or carry a suitable build in
   the feed.
3. Undo the workarounds below, then enable Passwall2 and finish the steps in #198.

## State of the test unit

Reversible, and off while `enabled='0'`:

- `ipset` and `libipset13` 7.17-1 installed with `--nodeps`. `hash:net` create, add, test and destroy all work. Each
  `ipset` command warns that the kernel supports protocol 6 only.
- The owner's UK node (VLESS over XHTTP with TLS, port 443) copied from their Linksys MX5300. Its address is an IPv6
  literal, so it depends on the WAN's IPv6 ([#50](https://github.com/mralinp/zlt-x28-openwrt/issues/50)).
- `/etc/config/passwall2` workarounds for this kernel and `dnsmasq`: `rulenode.default_node` set to that node,
  `rulenode.write_ipset_direct='0'`, `examplenode` deleted, `udp_no_redir_ports='1:65535'`, `localhost_proxy='0'`.
- Backups in `/root/backup-198` on the unit.

To undo:

```sh
ssh x28 'cp /root/backup-198/passwall2 /etc/config/passwall2 && opkg remove ipset libipset13'
```

Hostname nodes are not safe with this `dnsmasq`: Passwall2 writes an `ipset=` line for them, which brings the startup
failure back.

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

- Passwall2 starting on this unit, or how its scripts behave when the `-m socket` rules fail.
- Transparent proxying for LAN clients, and the cost of LAN forwarding.
- That the UDP exclusion and leak handling work. QUIC and client IPv6 would bypass the proxy until blocked.
- Any tunnel speed above 162 Mbit/s, and sustained heat under load.
- xray's `tun` inbound for UDP: `xray run -test` accepts it, but it has not been run. The installed Passwall2's sing-box
  generator has no XHTTP support, so sing-box can't use this node as it stands.
