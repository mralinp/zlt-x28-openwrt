# Getting started

## Install

Use **[x28-flasher](https://github.com/mralinp/x28-flasher)**. It is the only supported path; do not write partitions or change
the boot order by hand.

1. Connect the router with a **USB-A to USB-C** cable. USB-C to USB-C does not work (the preloader never sees the cable).
2. Follow the flasher's steps: connect, **verified full backup**, root access, prepare the image, flash, select the boot slot.
3. Keep a second copy of the backup offline. It holds the unit's identity (IMEI, MACs), calibration and credentials: never
   publish it, never use it on another unit.

The image goes to slot A. Stock firmware stays on slot B as the automatic fall-back **until the first firmware upgrade**, which
writes the slot that is not running ([Boot, slots and upgrades](Boot-Slots-and-Upgrades.md)).

> Flashing can brick the router. Read [Recovery and safety](Recovery-and-Safety.md) first.

## First login

| | |
|---|---|
| LuCI | `https://192.168.70.1/cgi-bin/luci` (self-signed certificate; HTTP redirects) |
| SSH | `ssh root@192.168.70.1`, port 22, LAN only |
| Password | empty until you set one (LuCI or `passwd`). SSH accepts a key at once; password login starts after you set one |
| Wi-Fi | check Network > Wireless and set your own key first thing. The first-boot default changed between releases (off with a random key in #224, open in #226), so do not assume it is protected |
| Cellular | `wan` comes up by itself with the APN read from the SIM |

## Everyday tasks

| Task | Where |
|---|---|
| APN, operator, band lock, cell lock, roaming | Network > Interfaces > `wan` > Carrier tab ([Cellular](Cellular-and-Telephony.md)) |
| Text messages, phone book, API keys | Services > Telephony |
| Install packages | System > Software, or `opkg update && opkg install <pkg>` ([Package feed](Package-Feed.md)) |
| Passwall2 | Services > Passwall2; ships **off**, add your own node first ([VPN](VPN-and-Passwall2.md)) |
| Firmware update | the notice on Status > Overview, or `x28-upgrade -y` |
| Check for an update without installing | `x28-upgrade --refresh` |
| Settings backup | System > Backup / Flash Firmware > Generate archive |
| Factory reset | hold the reset button 10 s (unit running, more than 3 min after boot), or LuCI "Perform reset", or `firstboot -y -r` |

## Upgrading firmware

Signed images are named `x28-sysupgrade-<version>.tar` on the
[releases page](https://github.com/mralinp/zlt-x28-openwrt/releases). Nothing installs by itself.

```sh
x28-upgrade            # show what is available (cached check)
x28-upgrade --refresh  # check again now; installs nothing
x28-upgrade -y         # download, check the hash and the signature, write the other slot, reboot
```

Back up your settings first. An upgrade keeps settings from the second upgrade on, and that is not fully verified; see
[Boot, slots and upgrades](Boot-Slots-and-Upgrades.md#what-is-kept).

## If something goes wrong

| Symptom | Do |
|---|---|
| LAN went dark after a Passwall2 change | `ssh x28 '/etc/init.d/passwall2 stop'` |
| No DHCP after boot on a PRO | wait about 35 s; `x28-dhcp` restarts `dnsmasq` by itself |
| `opkg update` fails on the `x28` feed | the feed line still says `releases/latest/download`: fix it as in [Package feed](Package-Feed.md#using-it) |
| A cell or band lock left you without service | remove the lock in the Carrier tab; manual undo commands are in [Cellular](Cellular-and-Telephony.md#locks) |
| The unit does not boot | after 6 failed tries the preloader boots the other slot. If both are bad: the flasher over USB ([Recovery](Recovery-and-Safety.md)) |

Full documents: [README](https://github.com/mralinp/zlt-x28-openwrt/blob/main/README.md),
[STATUS](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/STATUS.md).
