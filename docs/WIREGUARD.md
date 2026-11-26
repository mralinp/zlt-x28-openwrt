# WireGuard server on the X28

Reach the X28 and its LAN from anywhere (a phone on mobile data, a laptop abroad) through a WireGuard tunnel. It is the
standard OpenWrt setup: one `wireguard` interface in `/etc/config/network`, a firewall rule for its UDP port, and peers
whose configuration LuCI turns into a QR code. Nothing X28-specific is needed beyond what the image ships.

**What the image provides:** `kmod-wireguard` (our module for the vendor kernel, loaded by `x28-kmods`), `wireguard-tools`
and `luci-proto-wireguard` ([BUILD](BUILD.md#vpn-set-and-wireguard-in-the-image-230)).

**What you need:** a WAN address the peers can reach. A SIM with a **public IPv4** (for example a static IP from the
carrier) works directly. Most SIMs get a carrier-internal address (CGNAT, e.g. `10.x` or `25.x`) that no one outside can
reach; with one of those, a server on the X28 can't be reached over IPv4. Check under **Network > Interfaces > wan**: the
IPv4 address must be the one the internet sees.

## Server

LuCI: **Network > Interfaces > Add new interface**, name `wg0`, protocol **WireGuard VPN**, then **Generate new key pair**,
**Listen port** `51820`, **IP addresses** `10.28.0.1/24`. Under **Firewall Settings** put it in the `lan` zone, so tunnel
clients get the same access as the LAN (LuCI, SSH, the LAN devices). The same in a shell:

```sh
cp /etc/config/network /root/network.bak; cp /etc/config/firewall /root/firewall.bak
umask 077
uci set network.wg0=interface
uci set network.wg0.proto=wireguard
uci set network.wg0.private_key="$(wg genkey)"
uci set network.wg0.listen_port=51820
uci add_list network.wg0.addresses=10.28.0.1/24
uci commit network
Z=$(uci show firewall | sed -n "s/^firewall\.\([^.]*\)\.name='lan'$/\1/p")
uci add_list firewall.$Z.network=wg0
uci add firewall rule
uci set firewall.@rule[-1].name=Allow-WireGuard
uci set firewall.@rule[-1].src=wan
uci set firewall.@rule[-1].proto=udp
uci set firewall.@rule[-1].dest_port=51820
uci set firewall.@rule[-1].target=ACCEPT
uci commit firewall
ubus call network reload; ifup wg0; /etc/init.d/firewall reload
```

`Allow-WireGuard` is the only thing this opens on the WAN. LuCI and SSH stay closed to the internet: they are reached
through the tunnel. WireGuard answers only packets signed with a peer's key, so the open port does not show to a scan.

## Peers (phone, laptop)

One peer per device, each with its own address in `10.28.0.0/24`. LuCI: **Network > Interfaces > wg0 > Edit > Peers > Add
peer**: a description, **Generate new key pair**, **Allowed IPs** `10.28.0.2/32` (the next device `10.28.0.3/32`, and so
on), **Persistent keep alive** `25`. Leave **Route Allowed IPs** off. Save, then **Save & Apply**.

LuCI stores the peer's private key with the peer so it can build its configuration: open the peer again and click
**Generate configuration…**:

- **Connection endpoint:** the WAN's public IPv4 (or a DNS name for it).
- **Allowed IPs:** `10.28.0.0/24` and `192.168.1.0/24` reach the X28 and its LAN while the device's own internet stays
  on its own connection. `0.0.0.0/0` sends all its traffic through the X28 instead.
- **DNS:** `192.168.1.1` to use the X28's resolver, or empty.

LuCI draws the QR code in the browser (`uqr.js`) from the keys on the router; the keys don't leave the router and the
browser. On the phone: WireGuard app > **+** > **Scan from QR code**. For a laptop, download the configuration instead.
To revoke a device, delete its peer and **Save & Apply**.

## Check

From a device on another network (a phone with Wi-Fi off): turn the tunnel on and open `http://192.168.1.1`. On the X28:

```sh
wg show wg0     # the peer's endpoint, "latest handshake" under 2 minutes, transfer counters moving
```

No handshake: check that the WAN address is public and is the one in the peer's endpoint, that `Allow-WireGuard` is in
`iptables -S zone_wan_input`, and that the device is really outside the LAN.

## Notes

- **After a reboot** `wg0` comes up about 30 s late: `x28-kmods` loads the WireGuard module after `x28-bootok` has reset
  the boot tries, then brings up WireGuard interfaces ([BUILD](BUILD.md#vpn-set-and-wireguard-in-the-image-230)).
- **Updates** keep the server and peers: they live in `/etc/config/network` and `/etc/config/firewall`.
- **IPv6:** if the SIM has IPv6, add a ULA (e.g. `fd28::1/64`) to `wg0` and the peer's `/128` to its Allowed IPs. The
  endpoint can then also be the X28's public IPv6, which works even without a public IPv4.
- **Behind the X28's LAN** only what is on the X28's LAN is reachable. A router plugged into the X28 (its WAN on an X28
  LAN port) keeps its own LAN behind its own NAT.

## Tested

2026-11-24, v1.3.2, on a SIM with a static public IPv4 (`/28`, carrier-assigned):

- The server was set up as above.
- A phone joined over its own mobile data with Wi-Fi off, using the QR code from **Generate configuration…** and split routes.
- `wg show` showed the phone's mobile-data address as the endpoint, a handshake 27 s old, and 290 KiB received / 575 KiB sent.
- LuCI loaded over the tunnel.

Not tested: a reboot with the tunnel configured, full-tunnel routing (`0.0.0.0/0`), IPv6 inside the tunnel, a server on a
CGNAT SIM.
