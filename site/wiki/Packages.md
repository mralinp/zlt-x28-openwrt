# Packages

Everything we wrote lives in [`package/`](https://github.com/mralinp/zlt-x28-openwrt/tree/main/package).
[`x28-packages.ini`](https://github.com/mralinp/zlt-x28-openwrt/blob/main/package/x28-packages.ini) is the truth for what becomes
an `.ipk`: paths, modes, versions and dependencies. The image and the signed feed are made from the same ipks.

## The required set (`x28-base`)

`x28-base` is a meta-package that depends on all of these. While it is installed, `opkg remove` of a member is refused.

| Package | What it does | Main files |
|---|---|---|
| `x28-modem` | Starts the vendor modem stack at boot: daemons in order, mounts, the USB gadget the AT daemon needs, radio on, `ifup wan` | `/etc/init.d/x28-modem` |
| `x28-mipc` | The `x28_mipc` netifd protocol (IPv4, IPv6, IPv4v6, APN from the SIM) and its helpers | `/lib/netifd/proto/x28_mipc.sh`, `/sbin/x28-apn`, `/sbin/x28-modem-status`, `/sbin/x28-plmn-scan` |
| `luci-proto-x28-mipc` | The protocol's LuCI page and the Carrier tab | `protocol/x28_mipc.js`, an rpcd ACL |
| `x28-nrband` | 5G band lock and 5G signal over MIPC (the modem has no AT command for NR bands). Built against the unit's `libmipc_msg.so`, so built locally and pinned by hash | `/usr/sbin/x28-nrband` |
| `x28-telephony` | Text messages: LuCI pages, phone book, HTTP API, and a service that moves received messages off the SIM | `/usr/sbin/x28-sms`, `/etc/init.d/x28-telephony`, CGI, three LuCI views |
| `x28-wifi` | netifd wireless handler for the vendor `mt_wifi` driver, region and channel tables, the one-card or two-card profile, the WPS and reset button reader | `/lib/netifd/wireless/mtwifi.sh`, `/sbin/x28-wps`, `/sbin/x28-wifi-l1` |
| `x28-switch` | Loads the MT7531AE VLAN table so the four LAN sockets work; describes the switch to LuCI | `/etc/init.d/x28-switch`, `/etc/board.json` |
| `x28-dhcp` | Restarts `dnsmasq` if it came up without a DHCP range (the PRO's slow bridge) | `/etc/init.d/x28-dhcp`, `/usr/libexec/x28-dhcp-guard` |
| `x28-leds` | Front LEDs from radio, signal, WAN and Wi-Fi state through the vendor `tz_gpio_leds` driver | `/sbin/x28-leds` |
| `x28-bootok` | Resets the running slot's boot tries in `misc` after a good boot | `/etc/init.d/x28-bootok` |
| `x28-storage` | Attaches `user_data` as the overlay (about 278 MB); makes `firstboot` clear that overlay; the sysupgrade keep list | `/lib/preinit/79_x28_user_data`, `/sbin/firstboot` |
| `x28-kmods` | Loads our kernel modules about 30 s after boot, after the boot counter is reset; stops after three unfinished loads in a row | `/etc/init.d/x28-kmods`, lists in `/etc/x28-kmods.d/` |
| `x28-update` | Update notice on LuCI's Overview and `x28-upgrade` | `/usr/sbin/x28-upgrade`, `/usr/libexec/x28-update-check` |

## Image-only

| Package | Why it is not in the feed |
|---|---|
| `x28-sysupgrade` | `/lib/upgrade/platform.sh`, the `misc` writer and the verify step; it is the one reviewed exception to the build guard against flash writes |
| `x28-feed` | the feed's public key. The trust anchor must not update itself |
| `iwinfo-mtwifi` | a patch that gives `iwinfo` an `mt_wifi` backend (scan, channel, signal); ImageBuilder builds it |
| `x28-kmod-stubs` | the lists that say which official `kmod-*` names become stubs and which are real |

## Preinstalled, optional

`kmod-wireguard`, `kmod-ipt-tproxy`, `kmod-ipt-socket`, `ipset` with its libraries, OpenVPN, `dnsmasq-full`, and from its own
third-party feed Passwall2 with `xray`. Removing one is allowed; `opkg install` brings it back.

## Commands worth knowing

| Command | Does |
|---|---|
| `x28-modem-status` | operator, registration, locks, attach APN, serving and neighbour LTE cells (read-only) |
| `x28-plmn-scan` | network scan for manual operator selection |
| `x28-nrband signal` | 5G state and NR signal |
| `x28-sms` | lists its subcommands; output is JSON |
| `x28-upgrade [-y] [--refresh]` | show, install, or re-check firmware updates |
| `/etc/init.d/x28-kmods modules` | prints what the loader would load, in order |
| `x28-leds`, `x28-wps` | LED and button daemons; started by init |

## Updating and rolling back

- `opkg update && opkg upgrade` updates ours too. A package only changes when its version does.
- `x28-bootok`, `x28-kmods` and `x28-modem` are replaced on disk at once but take effect at the **next reboot**.
- Rolling back: this `opkg` cannot install from a URL. Download the older `.ipk` to `/tmp`, check its hash, then
  `opkg install --force-downgrade /tmp/<file>.ipk`. Tested with `x28-base`; the boot-critical ones were not rolled back.

## Rules for changing a package

- Bump `release` in `x28-packages.ini` whenever a package's files change; `opkg` only upgrades to a higher version.
- Shell is POSIX / busybox ash. Lua is 5.1 (no bit ops, no `//`). JS is vanilla, no build step.
- Anything non-trivial leaves one runnable check ([Development](Development.md#local-checks)).

Full documents: [PACKAGE-FEED](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/PACKAGE-FEED.md),
[MODULES](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/MODULES.md#software-map).
