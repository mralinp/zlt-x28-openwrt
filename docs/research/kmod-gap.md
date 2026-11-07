# Kmod gap analysis for the X28 feed (#394)

**2026-11-07, read-only.** Every kmod of the official OpenWrt 23.05.5 core feed (976) is sorted by what it would take to
make it work on the vendor 4.19.205 kernel. Input for #395 (build) and #396 (publish); epic #398.

| Class | Meaning | Count |
|---|---|---|
| A | already a stub: every module is on the unit or built in | 180 |
| B | **buildable out of tree**: 4.19 source exists and setting just its option `=m` changes no built-in symbol | 215 |
| C | **blocked**: source exists, but the option stays off or enabling it also changes built-in symbols (kernel config change) | 397 |
| D | **no 4.19 source** (module is newer than the kernel, or out of tree), or it needs a D kmod (backport or kernel change) | 184 |

A kmod takes the worst class of its own modules and of the kmods it depends on.

## What it says

- LuCI is not the problem. Only 2 `luci-*` packages depend directly on a C or D kmod (`luci-app-siitwizard`,
  `luci-proto-batman-adv`). LuCI already works; the gap is in other packages.
- 74 packages from base, packages and luci depend directly on a C or D kmod (not counting dependencies through libraries).
- B is where #395 works: 215 kmods, but many are hardware drivers (SATA, NICs) that make no sense on this SoC. The rows
  with user packages come first in the table, so build those first (`sched`/`sched-core`/`sched-cake` for SQM, `veth`,
  `macvlan`, `usbip`, `crypto-user`, `ipt-hashlimit`, `ipt-ipsec`, `bonding`, `inet-diag`, `netlink-diag`, `usb-acm`).
- The nftables, ksmbd, DES-based IPsec, Bluetooth and Wi-Fi (cfg80211) kmods are C or D. Unblocking them means a new kernel,
  which is #130 (`risk/brick`), or a backport.

## Limits (read before trusting a B)

- B is a Kconfig result, not a build or load result. It still needs a compile against the SDK tree and a load test on the
  unit (#395). The SDK tree has no `Module.symvers`, so modules carry no symbol versions ([CRC note](kernel-module-crc.md)).
- A module can compile and still fail to load if it uses a symbol the vendor kernel doesn't export.
- Option resolution used `make olddefconfig` on the SDK tree's `.config`, one option at a time. Class D "no 4.19 source"
  means no `obj-$(CONFIG_x) += name.o` line was found, so a module built by another rule can land here wrongly.
- Dependents are direct `Depends` only, from the aarch64_generic base, packages and luci indexes of 23.05.5.

## Reproduce

Needs the private SDK tree (volume `x28-kbuild`) and `ls /lib/modules/4.19.205/*.ko` from the unit.

```sh
python3 tools/build/kmod_gap.py --selftest
docker run --rm -v x28-kbuild:/k:ro -v "$PWD:/r:ro" -v "$PWD/out:/o" debian:bookworm bash -c '
  apt-get update -qq >/dev/null && apt-get install -y -qq --no-install-recommends python3 build-essential flex bison bc cpio ca-certificates >/dev/null
  mkdir /w && cd /k/linux && find . \( -name "Kconfig*" -o -name Makefile -o -name Kbuild -o -name modules.builtin -o -path "./scripts/*" \) -type f -print0 | cpio -0pdm /w 2>/dev/null
  cp .config /w/ && python3 /r/tools/build/kmod_gap.py --modules /o/modules.txt --tree /w --out /o/gap.md'
```

(The tree is copied because `olddefconfig` builds host tools in it.)

## Table

976 kmods: A 180, B 215, C 397, D 184

| Kmod | Class | Why | User packages that depend on it |
|---|---|---|---|
| `kmod-sched-core` | B | buildable | bridger, qos-scripts, tc-bpf, tc-full, tc-tiny, trafficshaper (+1) |
| `kmod-crypto-user` | B | buildable | cryptsetup, libopenssl-afalg, libopenssl-afalg_sync, strongswan-mod-af-alg |
| `kmod-usb-acm` | B | buildable | basicstation, bigclown-gateway, sx1302_hal-tests, sx1302_hal-utils |
| `kmod-ipt-ipset` | B | buildable | ipset, libipset13, pbr-iptables |
| `kmod-veth` | B | buildable | cni-plugins, dockerd, podman |
| `kmod-ipt-hashlimit` | B | buildable | shorewall, shorewall6 |
| `kmod-ipt-ipsec` | B | buildable | libreswan, strongswan-mod-updown |
| `kmod-nbd` | B | buildable | nbd, qemu-nbd |
| `kmod-sched` | B | buildable | luci-app-splash, tunneldigger-broker |
| `kmod-sched-bpf` | B | buildable | bridger, uspot |
| `kmod-sched-cake` | B | buildable | sqm-scripts, trafficshaper |
| `kmod-sched-connmark` | B | buildable | qos-scripts, trafficshaper |
| `kmod-spi-dev` | B | buildable | libloragw, spidev-test |
| `kmod-bonding` | B | buildable | proto-bonding |
| `kmod-crypto-chacha20poly1305` | B | buildable | strongswan-mod-chapoly |
| `kmod-inet-diag` | B | buildable | sing-box |
| `kmod-ipt-quota2` | B | buildable | iptables-mod-quota2 |
| `kmod-ipt-raw6` | B | buildable | shorewall6 |
| `kmod-iscsi-initiator` | B | buildable | open-iscsi |
| `kmod-leds-uleds` | B | buildable | bluld |
| `kmod-macvlan` | B | buildable | keepalived |
| `kmod-netlink-diag` | B | buildable | ss |
| `kmod-nfnetlink-log` | B | buildable | libnetfilter-log1 |
| `kmod-sched-act-vlan` | B | buildable | bridger |
| `kmod-sched-flower` | B | buildable | bridger |
| `kmod-usb-ledtrig-usbport` | B | buildable | luci-app-ledtrig-usbport |
| `kmod-usbip` | B | buildable | usbip |
| `kmod-3c59x` | B | buildable |  |
| `kmod-6lowpan` | B | buildable |  |
| `kmod-8139cp` | B | buildable |  |
| `kmod-aoe` | B | buildable |  |
| `kmod-ata-artop` | B | buildable |  |
| `kmod-ata-nvidia-sata` | B | buildable |  |
| `kmod-ata-pdc202xx-old` | B | buildable |  |
| `kmod-ata-piix` | B | buildable |  |
| `kmod-ata-sil` | B | buildable |  |
| `kmod-ata-via-sata` | B | buildable |  |
| `kmod-atl1` | B | buildable |  |
| `kmod-atl1c` | B | buildable |  |
| `kmod-atl1e` | B | buildable |  |
| `kmod-atl2` | B | buildable |  |
| `kmod-block2mtd` | B | buildable |  |
| `kmod-bpf-test` | B | buildable |  |
| `kmod-br-netfilter` | B | buildable |  |
| `kmod-chaoskey` | B | buildable |  |
| `kmod-crypto-fcrypt` | B | buildable |  |
| `kmod-crypto-md4` | B | buildable |  |
| `kmod-crypto-michael-mic` | B | buildable |  |
| `kmod-crypto-pcbc` | B | buildable |  |
| `kmod-crypto-rmd160` | B | buildable |  |
| `kmod-crypto-test` | B | buildable |  |
| `kmod-dax` | B | buildable |  |
| `kmod-dnsresolver` | B | buildable |  |
| `kmod-dummy` | B | buildable |  |
| `kmod-echo` | B | buildable |  |
| `kmod-eeprom-93cx6` | B | buildable |  |
| `kmod-eeprom-at24` | B | buildable |  |
| `kmod-et131x` | B | buildable |  |
| `kmod-ethoc` | B | buildable |  |
| `kmod-forcedeth` | B | buildable |  |
| `kmod-fou` | B | buildable |  |
| `kmod-fs-jfs` | B | buildable |  |
| `kmod-fs-minix` | B | buildable |  |
| `kmod-fs-msdos` | B | buildable |  |
| `kmod-fs-ntfs` | B | buildable |  |
| `kmod-fs-reiserfs` | B | buildable |  |
| `kmod-fs-vfat` | B | buildable |  |
| `kmod-fs-xfs` | B | buildable |  |
| `kmod-geneve` | B | buildable |  |
| `kmod-gpio-beeper` | B | buildable |  |
| `kmod-gpio-nxp-74hc164` | B | buildable |  |
| `kmod-gpio-pca953x` | B | buildable |  |
| `kmod-hwmon-core` | B | buildable |  |
| `kmod-hwmon-pwmfan` | B | buildable |  |
| `kmod-i2c-gpio` | B | buildable |  |
| `kmod-i2c-mux-gpio` | B | buildable |  |
| `kmod-i2c-mux-pca9541` | B | buildable |  |
| `kmod-i2c-tiny-usb` | B | buildable |  |
| `kmod-i6300esb-wdt` | B | buildable |  |
| `kmod-iio-bh1750` | B | buildable |  |
| `kmod-iio-bme680` | B | buildable |  |
| `kmod-iio-bmp280` | B | buildable |  |
| `kmod-iio-dht11` | B | buildable |  |
| `kmod-iio-si7020` | B | buildable |  |
| `kmod-iio-tsl4531` | B | buildable |  |
| `kmod-input-gpio-encoder` | B | buildable |  |
| `kmod-input-gpio-keys-polled` | B | buildable |  |
| `kmod-input-joydev` | B | buildable |  |
| `kmod-input-leds` | B | buildable |  |
| `kmod-input-matrixkmap` | B | buildable |  |
| `kmod-input-touchscreen-ads7846` | B | buildable |  |
| `kmod-input-touchscreen-edt-ft5x06` | B | buildable |  |
| `kmod-input-uinput` | B | buildable |  |
| `kmod-iosched-bfq` | B | buildable |  |
| `kmod-ip6tables-extra` | B | buildable |  |
| `kmod-ipt-checksum` | B | buildable |  |
| `kmod-ipt-cluster` | B | buildable |  |
| `kmod-ipt-debug` | B | buildable |  |
| `kmod-ipt-led` | B | buildable |  |
| `kmod-ipt-nflog` | B | buildable |  |
| `kmod-ipt-nfqueue` | B | buildable |  |
| `kmod-ipt-rpfilter` | B | buildable |  |
| `kmod-ipt-socket` | B | buildable |  |
| `kmod-ipt-tee` | B | buildable |  |
| `kmod-ipt-tproxy` | B | buildable |  |
| `kmod-ipt-u32` | B | buildable |  |
| `kmod-leds-pca955x` | B | buildable |  |
| `kmod-leds-pca963x` | B | buildable |  |
| `kmod-leds-tlc591xx` | B | buildable |  |
| `kmod-ledtrig-activity` | B | buildable |  |
| `kmod-ledtrig-gpio` | B | buildable |  |
| `kmod-ledtrig-oneshot` | B | buildable |  |
| `kmod-ledtrig-transient` | B | buildable |  |
| `kmod-lib-cordic` | B | buildable |  |
| `kmod-lkdtm` | B | buildable |  |
| `kmod-macsec` | B | buildable |  |
| `kmod-mdio-bcm-unimac` | B | buildable |  |
| `kmod-mdio-gpio` | B | buildable |  |
| `kmod-mmc-spi` | B | buildable |  |
| `kmod-mtdoops` | B | buildable |  |
| `kmod-netem` | B | buildable |  |
| `kmod-nf-dup-inet` | B | buildable |  |
| `kmod-nf-socket` | B | buildable |  |
| `kmod-nf-tproxy` | B | buildable |  |
| `kmod-nfnetlink-queue` | B | buildable |  |
| `kmod-niu` | B | buildable |  |
| `kmod-nlmon` | B | buildable |  |
| `kmod-nls-cp1250` | B | buildable |  |
| `kmod-nls-cp1251` | B | buildable |  |
| `kmod-nls-cp775` | B | buildable |  |
| `kmod-nls-cp850` | B | buildable |  |
| `kmod-nls-cp852` | B | buildable |  |
| `kmod-nls-cp862` | B | buildable |  |
| `kmod-nls-cp864` | B | buildable |  |
| `kmod-nls-cp866` | B | buildable |  |
| `kmod-nls-cp932` | B | buildable |  |
| `kmod-nls-cp936` | B | buildable |  |
| `kmod-nls-cp950` | B | buildable |  |
| `kmod-nls-iso8859-13` | B | buildable |  |
| `kmod-nls-iso8859-15` | B | buildable |  |
| `kmod-nls-iso8859-2` | B | buildable |  |
| `kmod-nls-iso8859-6` | B | buildable |  |
| `kmod-nls-iso8859-8` | B | buildable |  |
| `kmod-nls-koi8r` | B | buildable |  |
| `kmod-nls-utf8` | B | buildable |  |
| `kmod-nsh` | B | buildable |  |
| `kmod-phy-aquantia` | B | buildable |  |
| `kmod-phy-ax88796b` | B | buildable |  |
| `kmod-phy-bcm84881` | B | buildable |  |
| `kmod-phy-marvell` | B | buildable |  |
| `kmod-phy-marvell-10g` | B | buildable |  |
| `kmod-phy-microchip` | B | buildable |  |
| `kmod-phy-realtek` | B | buildable |  |
| `kmod-phy-smsc` | B | buildable |  |
| `kmod-pktgen` | B | buildable |  |
| `kmod-ppp-synctty` | B | buildable |  |
| `kmod-pps` | B | buildable |  |
| `kmod-r6040` | B | buildable |  |
| `kmod-r8169` | B | buildable |  |
| `kmod-rtc-ds1307` | B | buildable |  |
| `kmod-rtc-ds1374` | B | buildable |  |
| `kmod-rtc-ds1672` | B | buildable |  |
| `kmod-rtc-em3027` | B | buildable |  |
| `kmod-rtc-isl1208` | B | buildable |  |
| `kmod-rtc-pcf2123` | B | buildable |  |
| `kmod-rtc-pcf2127` | B | buildable |  |
| `kmod-rtc-pcf8563` | B | buildable |  |
| `kmod-rtc-rs5c372a` | B | buildable |  |
| `kmod-rtc-rx8025` | B | buildable |  |
| `kmod-rtc-s35390a` | B | buildable |  |
| `kmod-sched-act-ipt` | B | buildable |  |
| `kmod-sched-act-police` | B | buildable |  |
| `kmod-sched-act-sample` | B | buildable |  |
| `kmod-sched-ctinfo` | B | buildable |  |
| `kmod-sched-drr` | B | buildable |  |
| `kmod-sched-ipset` | B | buildable |  |
| `kmod-sched-mqprio` | B | buildable |  |
| `kmod-sched-pie` | B | buildable |  |
| `kmod-sched-prio` | B | buildable |  |
| `kmod-sched-red` | B | buildable |  |
| `kmod-sched-skbprio` | B | buildable |  |
| `kmod-scsi-generic` | B | buildable |  |
| `kmod-scsi-tape` | B | buildable |  |
| `kmod-sis190` | B | buildable |  |
| `kmod-sis900` | B | buildable |  |
| `kmod-slip` | B | buildable |  |
| `kmod-softdog` | B | buildable |  |
| `kmod-sound-dummy` | B | buildable |  |
| `kmod-sound-seq` | B | buildable |  |
| `kmod-spi-bitbang` | B | buildable |  |
| `kmod-spi-gpio` | B | buildable |  |
| `kmod-spi-ks8995` | B | buildable |  |
| `kmod-switch-bcm53xx` | B | buildable |  |
| `kmod-switch-ip17xx` | B | buildable |  |
| `kmod-switch-rtl8306` | B | buildable |  |
| `kmod-switch-rtl8366-smi` | B | buildable |  |
| `kmod-tcp-bbr` | B | buildable |  |
| `kmod-tcp-hybla` | B | buildable |  |
| `kmod-tcp-scalable` | B | buildable |  |
| `kmod-thermal` | B | buildable |  |
| `kmod-tls` | B | buildable |  |
| `kmod-usb-cm109` | B | buildable |  |
| `kmod-usb-printer` | B | buildable |  |
| `kmod-usb-serial` | B | buildable |  |
| `kmod-usb-storage-extras` | B | buildable |  |
| `kmod-usb-storage-uas` | B | buildable |  |
| `kmod-usb-test` | B | buildable |  |
| `kmod-usb-wdm` | B | buildable |  |
| `kmod-usb-yealink` | B | buildable |  |
| `kmod-usbmon` | B | buildable |  |
| `kmod-video-cpia2` | B | buildable |  |
| `kmod-video-gspca-core` | B | buildable |  |
| `kmod-vmxnet3` | B | buildable |  |
| `kmod-w1` | B | buildable |  |
| `kmod-wdt-sp805` | B | buildable |  |
| `kmod-nft-core` | C | nft_counter: CONFIG_NFT_COUNTER off; nft_ct: CONFIG_NFT_CT off; nft_hash: CONFIG_NFT_HASH off; nft_limit: CONFIG_NFT_LIMIT off; nft_log: CONFIG_NFT_LOG off; nft_numgen: CONFIG_NFT_NUMGEN off; nft_objref: CONFIG_NFT_OBJREF off; nft_quota: CONFIG_NFT_QUOTA off; nft_redir: CONFIG_NFT_REDIR off; nft_reject: CONFIG_NFT_REJECT off; nft_reject_inet: CONFIG_NFT_REJECT_INET off; nft_reject_ipv4: CONFIG_NFT_REJECT_IPV4 off; nft_reject_ipv6: CONFIG_NFT_REJECT_IPV6 off | firewall4, nftables-json, nftables-nojson, pbr |
| `kmod-wireguard` | C | wireguard: CONFIG_WIREGUARD also sets CONFIG_ARM64_CRYPTO=y; needs kmod-crypto-lib-chacha20poly1305 (C); needs kmod-crypto-lib-curve25519 (C) | unetd, wg-installer-client, wg-installer-server, wireguard-tools |
| `kmod-nf-ipvs` | C | ip_vs: CONFIG_IP_VS also sets CONFIG_IP_VS_MH_TAB_INDEX=12 CONFIG_IP_VS_SH_TAB_BITS=8 CONFIG_IP_VS_TAB_BITS=12; ip_vs_dh: CONFIG_IP_VS_DH off; ip_vs_fo: CONFIG_IP_VS_FO off; ip_vs_lblc: CONFIG_IP_VS_LBLC off; ip_vs_lblcr: CONFIG_IP_VS_LBLCR off; ip_vs_lc: CONFIG_IP_VS_LC off; ip_vs_nq: CONFIG_IP_VS_NQ off; ip_vs_ovf: CONFIG_IP_VS_OVF off; ip_vs_rr: CONFIG_IP_VS_RR off; ip_vs_sed: CONFIG_IP_VS_SED off; ip_vs_sh: CONFIG_IP_VS_SH off; ip_vs_wlc: CONFIG_IP_VS_WLC off; ip_vs_wrr: CONFIG_IP_VS_WRR off; xt_ipvs: CONFIG_NETFILTER_XT_MATCH_IPVS off | dockerd, ipvsadm, keepalived |
| `kmod-sit` | C | sit: CONFIG_IPV6_SIT also sets CONFIG_IPV6_NDISC_NODETYPE=y | 6in4, 6rd, 6to4 |
| `kmod-nft-netdev` | C | nf_dup_netdev: CONFIG_NF_DUP_NETDEV off; nft_dup_netdev: CONFIG_NFT_DUP_NETDEV off; nft_fwd_netdev: CONFIG_NFT_FWD_NETDEV off; needs kmod-nft-core (C) | nft-qos, phantap |
| `kmod-nft-queue` | C | nft_queue: CONFIG_NFT_QUEUE off; needs kmod-nft-core (C) | etherwake-nfqueue, snort3 |
| `kmod-nft-tproxy` | C | nft_tproxy: CONFIG_NFT_TPROXY off; needs kmod-nft-core (C) | shadowsocks-libev-ss-rules, v2raya |
| `kmod-arptables` | C | arp_tables: CONFIG_IP_NF_ARPTABLES also sets CONFIG_NETFILTER_FAMILY_ARP=y; arpt_mangle: CONFIG_IP_NF_ARP_MANGLE off; arptable_filter: CONFIG_IP_NF_ARPFILTER off | arptables-legacy |
| `kmod-batman-adv` | C | batman-adv: CONFIG_BATMAN_ADV also sets CONFIG_BATMAN_ADV_BATMAN_V=y CONFIG_BATMAN_ADV_BLA=y CONFIG_BATMAN_ADV_DAT=y; needs kmod-cfg80211 (C) | luci-proto-batman-adv |
| `kmod-fs-nfs` | C | nfs: CONFIG_NFS_FS also sets CONFIG_LOCKD_V4=y CONFIG_NFS_COMMON=y; needs kmod-fs-nfs-common (C) | nfs-kernel-server |
| `kmod-fs-nfs-v4` | C | nfsv4: CONFIG_NFS_V4 off; needs kmod-fs-nfs (C) | nfs-kernel-server |
| `kmod-ipt-physdev` | C | xt_physdev: CONFIG_NETFILTER_XT_MATCH_PHYSDEV off | dockerd |
| `kmod-md-mod` | C | md-mod: CONFIG_BLK_DEV_MD off | mdadm |
| `kmod-md-raid0` | C | raid0: CONFIG_MD_RAID0 off; needs kmod-md-mod (C) | mdadm |
| `kmod-md-raid1` | C | raid1: CONFIG_MD_RAID1 off; needs kmod-md-mod (C) | mdadm |
| `kmod-md-raid10` | C | raid10: CONFIG_MD_RAID10 off; needs kmod-md-mod (C) | mdadm |
| `kmod-mt76-core` | C | mt76: CONFIG_MT76_CORE off; needs kmod-mac80211 (C) | mt76-test |
| `kmod-nft-fib` | C | nft_fib: CONFIG_NFT_FIB off; nft_fib_inet: CONFIG_NFT_FIB_INET off; nft_fib_ipv4: CONFIG_NFT_FIB_IPV4 off; nft_fib_ipv6: CONFIG_NFT_FIB_IPV6 off; needs kmod-nft-core (C) | firewall4 |
| `kmod-openvswitch` | C | openvswitch: CONFIG_OPENVSWITCH also sets CONFIG_MPLS=y; needs kmod-mpls (C) | openvswitch |
| `kmod-pppoa` | C | pppoatm: CONFIG_PPPOATM off; needs kmod-atm (C) | ppp-mod-pppoa |
| `kmod-sctp` | C | sctp: CONFIG_IP_SCTP also sets CONFIG_SCTP_COOKIE_HMAC_MD5=y CONFIG_SCTP_DEFAULT_COOKIE_HMAC_MD5=y | libsctp |
| `kmod-solos-pci` | C | solos-pci: CONFIG_ATM_SOLOS off; needs kmod-atm (C) | soloscli |
| `kmod-usb-serial-ch341` | C | ch341: CONFIG_USB_SERIAL_CH341 off | gl-puli-mcu |
| `kmod-usb-serial-ftdi` | C | ftdi_sio: CONFIG_USB_SERIAL_FTDI_SIO off | bigclown-gateway |
| `kmod-usbip-client` | C | vhci-hcd: CONFIG_USBIP_VHCI_HCD off | usbip-client |
| `kmod-usbip-server` | C | usbip-host: CONFIG_USBIP_HOST off | usbip-server |
| `kmod-8139too` | C | 8139too: CONFIG_8139TOO also sets CONFIG_8139TOO_PIO=y |  |
| `kmod-ac97` | C | ac97_bus: CONFIG_AC97_BUS off; snd-ac97-codec: CONFIG_SND_AC97_CODEC off |  |
| `kmod-alx` | C | needs kmod-mdio (C) |  |
| `kmod-ar5523` | C | ar5523: CONFIG_AR5523 off; needs kmod-mac80211 (C); needs kmod-ath (C) |  |
| `kmod-asn1-decoder` | C | asn1_decoder: CONFIG_ASN1 off |  |
| `kmod-at86rf230` | C | at86rf230: CONFIG_IEEE802154_AT86RF230 off; needs kmod-mac802154 (C) |  |
| `kmod-ath` | C | ath: CONFIG_ATH_COMMON off; needs kmod-mac80211 (C) |  |
| `kmod-ath10k` | C | ath10k_core: CONFIG_ATH10K off; ath10k_pci: CONFIG_ATH10K_PCI off; needs kmod-ath (C) |  |
| `kmod-ath10k-ct` | C | ath10k_core: CONFIG_ATH10K off; ath10k_pci: CONFIG_ATH10K_PCI off; needs kmod-mac80211 (C); needs kmod-ath (C) |  |
| `kmod-ath10k-ct-smallbuffers` | C | ath10k_core: CONFIG_ATH10K off; ath10k_pci: CONFIG_ATH10K_PCI off; needs kmod-mac80211 (C); needs kmod-ath (C) |  |
| `kmod-ath10k-smallbuffers` | C | ath10k_core: CONFIG_ATH10K off; ath10k_pci: CONFIG_ATH10K_PCI off; needs kmod-ath (C) |  |
| `kmod-ath5k` | C | ath5k: CONFIG_ATH5K off; needs kmod-ath (C) |  |
| `kmod-ath6kl` | C | ath6kl_core: CONFIG_ATH6KL off; needs kmod-ath (C) |  |
| `kmod-ath6kl-sdio` | C | ath6kl_sdio: CONFIG_ATH6KL_SDIO off; needs kmod-ath6kl (C) |  |
| `kmod-ath6kl-usb` | C | ath6kl_usb: CONFIG_ATH6KL_USB off; needs kmod-ath6kl (C) |  |
| `kmod-ath9k` | C | ath9k: CONFIG_ATH9K off; needs kmod-ath9k-common (C) |  |
| `kmod-ath9k-common` | C | ath9k_common: CONFIG_ATH9K_COMMON off; ath9k_hw: CONFIG_ATH9K_HW off; needs kmod-ath (C) |  |
| `kmod-ath9k-htc` | C | ath9k_htc: CONFIG_ATH9K_HTC off; needs kmod-ath9k-common (C) |  |
| `kmod-atlantic` | C | atlantic: CONFIG_AQTION off; needs kmod-ptp (C) |  |
| `kmod-atm` | C | atm: CONFIG_ATM also sets CONFIG_ATM_DRIVERS=y; br2684: CONFIG_ATM_BR2684 off |  |
| `kmod-atmtcp` | C | atmtcp: CONFIG_ATM_TCP off; needs kmod-atm (C) |  |
| `kmod-atusb` | C | atusb: CONFIG_IEEE802154_ATUSB off; needs kmod-mac802154 (C) |  |
| `kmod-ax25` | C | ax25: CONFIG_AX25 off; mkiss: CONFIG_MKISS off |  |
| `kmod-b43` | C | b43: CONFIG_B43 off; needs kmod-mac80211 (C); needs kmod-ssb (C); needs kmod-bcma (C) |  |
| `kmod-b44` | C | b44: CONFIG_B44 off; needs kmod-ssb (C) |  |
| `kmod-bcma` | C | bcma: CONFIG_BCMA also sets CONFIG_BCMA_BLOCKIO=y CONFIG_BCMA_DRIVER_PCI=y CONFIG_BCMA_HOST_PCI=y |  |
| `kmod-bcmgenet` | C | genet: CONFIG_BCMGENET off |  |
| `kmod-be2net` | C | be2net: CONFIG_BE2NET also sets CONFIG_BE2NET_BE2=y CONFIG_BE2NET_BE3=y CONFIG_BE2NET_LANCER=y |  |
| `kmod-bnx2` | C | bnx2: CONFIG_BNX2 off |  |
| `kmod-bnx2x` | C | bnx2x: CONFIG_BNX2X off; needs kmod-mdio (C); needs kmod-ptp (C) |  |
| `kmod-brcmfmac` | C | brcmfmac: CONFIG_BRCMFMAC off; needs kmod-cfg80211 (C); needs kmod-brcmutil (C) |  |
| `kmod-brcmsmac` | C | brcmsmac: CONFIG_BRCMSMAC off; needs kmod-mac80211 (C); needs kmod-bcma (C); needs kmod-brcmutil (C) |  |
| `kmod-brcmutil` | C | brcmutil: CONFIG_BRCMUTIL off |  |
| `kmod-ca8210` | C | ca8210: CONFIG_IEEE802154_CA8210 off; needs kmod-mac802154 (C) |  |
| `kmod-can` | C | can: CONFIG_CAN also sets CONFIG_CAN_CALC_BITTIMING=y; can-dev: CONFIG_CAN_DEV off |  |
| `kmod-can-bcm` | C | can-bcm: CONFIG_CAN_BCM off; needs kmod-can (C) |  |
| `kmod-can-c-can` | C | c_can: CONFIG_CAN_C_CAN off; needs kmod-can (C) |  |
| `kmod-can-c-can-pci` | C | c_can_pci: CONFIG_CAN_C_CAN_PCI off; needs kmod-can-c-can (C); needs kmod-can (C) |  |
| `kmod-can-c-can-platform` | C | c_can_platform: CONFIG_CAN_C_CAN_PLATFORM off; needs kmod-can-c-can (C); needs kmod-can (C) |  |
| `kmod-can-gw` | C | can-gw: CONFIG_CAN_GW off; needs kmod-can (C) |  |
| `kmod-can-mcp251x` | C | mcp251x: CONFIG_CAN_MCP251X off; needs kmod-can (C) |  |
| `kmod-can-raw` | C | can-raw: CONFIG_CAN_RAW off; needs kmod-can (C) |  |
| `kmod-can-slcan` | C | slcan: CONFIG_CAN_SLCAN off; needs kmod-can (C) |  |
| `kmod-can-usb-8dev` | C | usb_8dev: CONFIG_CAN_8DEV_USB off; needs kmod-can (C) |  |
| `kmod-can-usb-ems` | C | ems_usb: CONFIG_CAN_EMS_USB off; needs kmod-can (C) |  |
| `kmod-can-usb-esd` | C | esd_usb2: CONFIG_CAN_ESD_USB2 off; needs kmod-can (C) |  |
| `kmod-can-usb-kvaser` | C | kvaser_usb: CONFIG_CAN_KVASER_USB off; needs kmod-can (C) |  |
| `kmod-can-usb-peak` | C | peak_usb: CONFIG_CAN_PEAK_USB off; needs kmod-can (C) |  |
| `kmod-can-vcan` | C | vcan: CONFIG_CAN_VCAN off; needs kmod-can (C) |  |
| `kmod-carl9170` | C | carl9170: CONFIG_CARL9170 off; needs kmod-mac80211 (C); needs kmod-ath (C) |  |
| `kmod-cc2520` | C | cc2520: CONFIG_IEEE802154_CC2520 off; needs kmod-mac802154 (C) |  |
| `kmod-cdrom` | C | cdrom: CONFIG_CDROM off |  |
| `kmod-cfg80211` | C | cfg80211: CONFIG_CFG80211 also sets CONFIG_ASN1=y CONFIG_ASYMMETRIC_KEY_TYPE=y CONFIG_ASYMMETRIC_PUBLIC_KEY_SUBTYPE=y; compat: CONFIG_COMPAT off; CONFIG_KEYS_COMPAT off; CONFIG_QUOTACTL_COMPAT off; CONFIG_SYSVIPC_COMPAT off |  |
| `kmod-crypto-lib-chacha20poly1305` | C | needs kmod-crypto-lib-poly1305 (C) |  |
| `kmod-crypto-lib-curve25519` | C | libcurve25519-generic: CONFIG_CRYPTO_LIB_CURVE25519_GENERIC off |  |
| `kmod-crypto-lib-poly1305` | C | poly1305-neon: CONFIG_CRYPTO_POLY1305_NEON off |  |
| `kmod-crypto-misc` | C | cast_common: CONFIG_CRYPTO_CAST_COMMON off; twofish_common: CONFIG_CRYPTO_TWOFISH_COMMON off |  |
| `kmod-e100` | C | e100: CONFIG_E100 off |  |
| `kmod-e1000` | C | e1000: CONFIG_E1000 off |  |
| `kmod-e1000e` | C | e1000e: CONFIG_E1000E off; needs kmod-ptp (C) |  |
| `kmod-fakelb` | C | fakelb: CONFIG_IEEE802154_FAKELB off; needs kmod-mac802154 (C) |  |
| `kmod-fb-tft` | C | fbtft: CONFIG_FB_TFT also sets CONFIG_FB_BACKLIGHT=y |  |
| `kmod-fb-tft-ili9486` | C | fb_ili9486: CONFIG_FB_TFT_ILI9486 off; needs kmod-fb-tft (C) |  |
| `kmod-firewire` | C | firewire-core: CONFIG_FIREWIRE also sets CONFIG_SND_FIREWIRE=y |  |
| `kmod-firewire-net` | C | firewire-net: CONFIG_FIREWIRE_NET off; needs kmod-firewire (C) |  |
| `kmod-firewire-ohci` | C | firewire-ohci: CONFIG_FIREWIRE_OHCI off; needs kmod-firewire (C) |  |
| `kmod-firewire-sbp2` | C | firewire-sbp2: CONFIG_FIREWIRE_SBP2 off; needs kmod-firewire (C) |  |
| `kmod-fou6` | C | fou6: CONFIG_IPV6_FOU off |  |
| `kmod-fs-cramfs` | C | cramfs: CONFIG_CRAMFS also sets CONFIG_CRAMFS_BLOCKDEV=y |  |
| `kmod-fs-hfs` | C | needs kmod-cdrom (C) |  |
| `kmod-fs-hfsplus` | C | needs kmod-cdrom (C) |  |
| `kmod-fs-isofs` | C | needs kmod-cdrom (C) |  |
| `kmod-fs-nfs-common` | C | grace: CONFIG_GRACE_PERIOD off; lockd: CONFIG_LOCKD off; sunrpc: CONFIG_SUNRPC off; needs kmod-oid-registry (C) |  |
| `kmod-fs-nfs-v3` | C | nfsv3: CONFIG_NFS_V3 off; needs kmod-fs-nfs (C) |  |
| `kmod-fs-udf` | C | needs kmod-cdrom (C) |  |
| `kmod-fsl-dpaa1-net` | C | needs kmod-fsl-xgmac-mdio (C) |  |
| `kmod-fsl-fec` | C | fec: CONFIG_FEC off; needs kmod-ptp (C) |  |
| `kmod-fsl-mc-dpio` | C | fsl-mc-dpio: CONFIG_FSL_MC_DPIO off |  |
| `kmod-fsl-xgmac-mdio` | C | xgmac_mdio: CONFIG_FSL_XGMAC_MDIO off |  |
| `kmod-google-firmware` | C | coreboot_table: CONFIG_GOOGLE_COREBOOT_TABLE off; memconsole: CONFIG_GOOGLE_MEMCONSOLE off; memconsole-coreboot: CONFIG_GOOGLE_MEMCONSOLE_COREBOOT off; vpd-sysfs: CONFIG_GOOGLE_VPD off |  |
| `kmod-gpio-pcf857x` | C | gpio-pcf857x: CONFIG_GPIO_PCF857X also sets CONFIG_GPIOLIB_IRQCHIP=y |  |
| `kmod-hfcmulti` | C | hfcmulti: CONFIG_MISDN_HFCMULTI off; needs kmod-misdn (C) |  |
| `kmod-hfcpci` | C | hfcpci: CONFIG_MISDN_HFCPCI off; needs kmod-misdn (C) |  |
| `kmod-hwmon-ad7418` | C | ad7418: CONFIG_SENSORS_AD7418 off |  |
| `kmod-hwmon-adcxx` | C | adcxx: CONFIG_SENSORS_ADCXX off |  |
| `kmod-hwmon-adt7410` | C | adt7410: CONFIG_SENSORS_ADT7410 off; adt7x10: CONFIG_SENSORS_ADT7X10 off |  |
| `kmod-hwmon-adt7475` | C | adt7475: CONFIG_SENSORS_ADT7475 off; needs kmod-hwmon-vid (C) |  |
| `kmod-hwmon-dme1737` | C | dme1737: CONFIG_SENSORS_DME1737 off; needs kmod-hwmon-vid (C) |  |
| `kmod-hwmon-g762` | C | g762: CONFIG_SENSORS_G762 off |  |
| `kmod-hwmon-gpiofan` | C | gpio-fan: CONFIG_SENSORS_GPIO_FAN off |  |
| `kmod-hwmon-ina209` | C | ina209: CONFIG_SENSORS_INA209 off |  |
| `kmod-hwmon-ina2xx` | C | ina2xx: CONFIG_SENSORS_INA2XX off |  |
| `kmod-hwmon-it87` | C | it87: CONFIG_SENSORS_IT87 off; needs kmod-hwmon-vid (C) |  |
| `kmod-hwmon-lm63` | C | lm63: CONFIG_SENSORS_LM63 off |  |
| `kmod-hwmon-lm70` | C | lm70: CONFIG_SENSORS_LM70 off |  |
| `kmod-hwmon-lm75` | C | lm75: CONFIG_SENSORS_LM75 off |  |
| `kmod-hwmon-lm77` | C | lm77: CONFIG_SENSORS_LM77 off |  |
| `kmod-hwmon-lm85` | C | lm85: CONFIG_SENSORS_LM85 off; needs kmod-hwmon-vid (C) |  |
| `kmod-hwmon-lm90` | C | lm90: CONFIG_SENSORS_LM90 off |  |
| `kmod-hwmon-lm92` | C | lm92: CONFIG_SENSORS_LM92 off |  |
| `kmod-hwmon-lm95241` | C | lm95241: CONFIG_SENSORS_LM95241 off |  |
| `kmod-hwmon-ltc4151` | C | ltc4151: CONFIG_SENSORS_LTC4151 off |  |
| `kmod-hwmon-max6642` | C | max6642: CONFIG_SENSORS_MAX6642 off |  |
| `kmod-hwmon-mcp3021` | C | mcp3021: CONFIG_SENSORS_MCP3021 off |  |
| `kmod-hwmon-nct7802` | C | nct7802: CONFIG_SENSORS_NCT7802 off |  |
| `kmod-hwmon-sch5627` | C | sch5627: CONFIG_SENSORS_SCH5627 off; sch56xx-common: CONFIG_SENSORS_SCH56XX_COMMON off |  |
| `kmod-hwmon-sht21` | C | sht21: CONFIG_SENSORS_SHT21 off |  |
| `kmod-hwmon-sht3x` | C | sht3x: CONFIG_SENSORS_SHT3x off |  |
| `kmod-hwmon-tmp102` | C | tmp102: CONFIG_SENSORS_TMP102 off |  |
| `kmod-hwmon-tmp103` | C | tmp103: CONFIG_SENSORS_TMP103 off |  |
| `kmod-hwmon-tmp421` | C | tmp421: CONFIG_SENSORS_TMP421 off |  |
| `kmod-hwmon-vid` | C | hwmon-vid: CONFIG_HWMON_VID off |  |
| `kmod-hwmon-w83793` | C | w83793: CONFIG_SENSORS_W83793 off; needs kmod-hwmon-vid (C) |  |
| `kmod-i2c-algo-pca` | C | i2c-algo-pca: CONFIG_I2C_ALGOPCA off |  |
| `kmod-i2c-algo-pcf` | C | i2c-algo-pcf: CONFIG_I2C_ALGOPCF off |  |
| `kmod-i2c-designware-core` | C | i2c-designware-core: CONFIG_I2C_DESIGNWARE_CORE off |  |
| `kmod-i2c-designware-pci` | C | needs kmod-i2c-designware-core (C) |  |
| `kmod-i2c-pxa` | C | i2c-pxa: CONFIG_I2C_PXA off |  |
| `kmod-i40e` | C | i40e: CONFIG_I40E off; needs kmod-mdio (C); needs kmod-ptp (C) |  |
| `kmod-ieee802154` | C | ieee802154_socket: CONFIG_IEEE802154_SOCKET off |  |
| `kmod-ieee802154-6lowpan` | C | ieee802154_6lowpan: CONFIG_IEEE802154_6LOWPAN off; needs kmod-ieee802154 (C) |  |
| `kmod-igb` | C | igb: CONFIG_IGB off; needs kmod-ptp (C) |  |
| `kmod-iio-ad799x` | C | ad799x: CONFIG_AD799X also sets CONFIG_IIO_BUFFER=y CONFIG_IIO_CONSUMERS_PER_TRIGGER=2 CONFIG_IIO_TRIGGER=y; needs kmod-industrialio-triggered-buffer (C) |  |
| `kmod-iio-ads1015` | C | ti-ads1015: CONFIG_TI_ADS1015 also sets CONFIG_IIO_BUFFER=y CONFIG_IIO_CONSUMERS_PER_TRIGGER=2 CONFIG_IIO_TRIGGER=y; needs kmod-industrialio-triggered-buffer (C) |  |
| `kmod-iio-am2315` | C | am2315: CONFIG_AM2315 also sets CONFIG_IIO_BUFFER=y CONFIG_IIO_CONSUMERS_PER_TRIGGER=2 CONFIG_IIO_TRIGGER=y; needs kmod-industrialio-triggered-buffer (C) |  |
| `kmod-iio-bme680-i2c` | C | bme680_i2c: CONFIG_BME680_I2C off |  |
| `kmod-iio-bme680-spi` | C | bme680_spi: CONFIG_BME680_SPI off |  |
| `kmod-iio-bmp280-i2c` | C | bmp280-i2c: CONFIG_BMP280_I2C off |  |
| `kmod-iio-bmp280-spi` | C | bmp280-spi: CONFIG_BMP280_SPI off |  |
| `kmod-iio-ccs811` | C | ccs811: CONFIG_CCS811 also sets CONFIG_IIO_BUFFER=y CONFIG_IIO_CONSUMERS_PER_TRIGGER=2 CONFIG_IIO_TRIGGER=y; needs kmod-industrialio-triggered-buffer (C) |  |
| `kmod-iio-hmc5843` | C | hmc5843_core: CONFIG_SENSORS_HMC5843 off; hmc5843_i2c: CONFIG_SENSORS_HMC5843_I2C also sets CONFIG_IIO_BUFFER=y CONFIG_IIO_CONSUMERS_PER_TRIGGER=2 CONFIG_IIO_TRIGGER=y; needs kmod-industrialio-triggered-buffer (C) |  |
| `kmod-iio-htu21` | C | ms_sensors_i2c: CONFIG_IIO_MS_SENSORS_I2C off |  |
| `kmod-iio-kfifo-buf` | C | kfifo_buf: CONFIG_IIO_KFIFO_BUF off |  |
| `kmod-iio-lsm6dsx` | C | st_lsm6dsx: CONFIG_IIO_ST_LSM6DSX also sets CONFIG_IIO_BUFFER=y; needs kmod-iio-kfifo-buf (C) |  |
| `kmod-iio-lsm6dsx-i2c` | C | st_lsm6dsx_i2c: CONFIG_IIO_ST_LSM6DSX_I2C off; needs kmod-iio-lsm6dsx (C) |  |
| `kmod-iio-lsm6dsx-spi` | C | st_lsm6dsx_spi: CONFIG_IIO_ST_LSM6DSX_SPI off; needs kmod-iio-lsm6dsx (C) |  |
| `kmod-iio-st_accel` | C | st_sensors: CONFIG_IIO_ST_SENSORS_CORE off; needs kmod-industrialio-triggered-buffer (C) |  |
| `kmod-iio-st_accel-i2c` | C | st_accel_i2c: CONFIG_IIO_ST_ACCEL_I2C_3AXIS off; st_sensors_i2c: CONFIG_IIO_ST_SENSORS_I2C off; needs kmod-iio-st_accel (C) |  |
| `kmod-iio-st_accel-spi` | C | st_accel_spi: CONFIG_IIO_ST_ACCEL_SPI_3AXIS off; st_sensors_spi: CONFIG_IIO_ST_SENSORS_SPI off; needs kmod-iio-st_accel (C) |  |
| `kmod-industrialio-triggered-buffer` | C | industrialio-triggered-buffer: CONFIG_IIO_TRIGGERED_BUFFER off; needs kmod-iio-kfifo-buf (C) |  |
| `kmod-ipoa` | C | clip: CONFIG_ATM_CLIP off; needs kmod-atm (C) |  |
| `kmod-ipt-clusterip` | C | ipt_CLUSTERIP: CONFIG_IP_NF_TARGET_CLUSTERIP also sets CONFIG_NETFILTER_FAMILY_ARP=y |  |
| `kmod-ipt-conntrack-label` | C | xt_connlabel: CONFIG_NETFILTER_XT_MATCH_CONNLABEL also sets CONFIG_NF_CONNTRACK_LABELS=y |  |
| `kmod-ipt-extra` | C | xt_cgroup: CONFIG_NETFILTER_XT_MATCH_CGROUP also sets CONFIG_CGROUP_NET_CLASSID=y CONFIG_SOCK_CGROUP_DATA=y |  |
| `kmod-ipt-offload` | C | xt_FLOWOFFLOAD: CONFIG_NETFILTER_XT_TARGET_FLOWOFFLOAD off; needs kmod-nf-flow (C) |  |
| `kmod-ipvlan` | C | ipvlan: CONFIG_IPVLAN also sets CONFIG_NET_L3_MASTER_DEV=y |  |
| `kmod-iwlwifi` | C | iwldvm: CONFIG_IWLDVM off; iwlmvm: CONFIG_IWLMVM off; iwlwifi: CONFIG_IWLWIFI off; needs kmod-mac80211 (C) |  |
| `kmod-ixgbe` | C | ixgbe: CONFIG_IXGBE off; needs kmod-mdio (C); needs kmod-ptp (C) |  |
| `kmod-ixgbevf` | C | ixgbevf: CONFIG_IXGBEVF off; needs kmod-ixgbe (C) |  |
| `kmod-lan743x` | C | needs kmod-ptp (C) |  |
| `kmod-leds-lp5562` | C | leds-lp5562: CONFIG_LEDS_LP5562 also sets CONFIG_FW_LOADER_USER_HELPER=y; needs kmod-leds-lp55xx-common (C) |  |
| `kmod-leds-lp55xx-common` | C | leds-lp55xx-common: CONFIG_LEDS_LP55XX_COMMON off |  |
| `kmod-lib-842` | C | 842_compress: CONFIG_842_COMPRESS off; 842_decompress: CONFIG_842_DECOMPRESS off |  |
| `kmod-lib-lz4hc` | C | lz4hc_compress: CONFIG_LZ4HC_COMPRESS off |  |
| `kmod-lib-raid6` | C | raid6_pq: CONFIG_RAID6_PQ off |  |
| `kmod-lib-xor` | C | xor: CONFIG_XOR_BLOCKS off; xor-neon: CONFIG_XOR_BLOCKS off |  |
| `kmod-lib-zstd` | C | zstd_compress: CONFIG_ZSTD_COMPRESS off; zstd_decompress: CONFIG_ZSTD_DECOMPRESS off |  |
| `kmod-lp` | C | lp: CONFIG_PRINTER off; needs kmod-ppdev (C) |  |
| `kmod-mac80211` | C | mac80211: CONFIG_MAC80211 off; needs kmod-cfg80211 (C) |  |
| `kmod-mac80211-hwsim` | C | mac80211_hwsim: CONFIG_MAC80211_HWSIM off; needs kmod-mac80211 (C) |  |
| `kmod-mac802154` | C | mac802154: CONFIG_MAC802154 off; needs kmod-ieee802154 (C) |  |
| `kmod-md-linear` | C | linear: CONFIG_MD_LINEAR off; needs kmod-md-mod (C) |  |
| `kmod-md-multipath` | C | multipath: CONFIG_MD_MULTIPATH off; needs kmod-md-mod (C) |  |
| `kmod-md-raid456` | C | async_memcpy: CONFIG_ASYNC_MEMCPY off; async_pq: CONFIG_ASYNC_PQ off; async_raid6_recov: CONFIG_ASYNC_RAID6_RECOV off; async_tx: CONFIG_ASYNC_CORE off; async_xor: CONFIG_ASYNC_XOR off; raid456: CONFIG_MD_RAID456 off; needs kmod-md-mod (C); needs kmod-lib-raid6 (C); needs kmod-lib-xor (C) |  |
| `kmod-mdio` | C | mdio: CONFIG_MDIO off |  |
| `kmod-mdio-thunder` | C | mdio-cavium: CONFIG_MDIO_CAVIUM off |  |
| `kmod-misdn` | C | l1oip: CONFIG_MISDN_L1OIP off; mISDN_core: CONFIG_MISDN off; mISDN_dsp: CONFIG_MISDN_DSP off |  |
| `kmod-mlx4-core` | C | mlx4_core: CONFIG_MLX4_CORE off; mlx4_en: CONFIG_MLX4_EN off; needs kmod-ptp (C) |  |
| `kmod-mlx5-core` | C | mlx5_core: CONFIG_MLX5_CORE off; needs kmod-ptp (C) |  |
| `kmod-mpls` | C | mpls_gso: CONFIG_NET_MPLS_GSO off; mpls_iptunnel: CONFIG_MPLS_IPTUNNEL off; mpls_router: CONFIG_MPLS_ROUTING off |  |
| `kmod-mrf24j40` | C | mrf24j40: CONFIG_IEEE802154_MRF24J40 off; needs kmod-mac802154 (C) |  |
| `kmod-mt76-usb` | C | mt76-usb: CONFIG_MT76_USB off; needs kmod-mac80211 (C); needs kmod-mt76-core (C) |  |
| `kmod-mt7601u` | C | mt7601u: CONFIG_MT7601U off; needs kmod-mac80211 (C) |  |
| `kmod-mt7663-firmware-ap` | C | needs kmod-mac80211 (C) |  |
| `kmod-mt7663-firmware-sta` | C | needs kmod-mac80211 (C) |  |
| `kmod-mt7921-firmware` | C | needs kmod-mac80211 (C) |  |
| `kmod-mt7922-firmware` | C | needs kmod-mac80211 (C) |  |
| `kmod-mtdram` | C | mtdram: CONFIG_MTD_MTDRAM also sets CONFIG_MTDRAM_ERASE_SIZE=128 CONFIG_MTDRAM_TOTAL_SIZE=4096 |  |
| `kmod-mux-core` | C | mux-core: CONFIG_MULTIPLEXER off |  |
| `kmod-mux-gpio` | C | mux-gpio: CONFIG_MUX_GPIO off; needs kmod-mux-core (C) |  |
| `kmod-mvneta` | C | mvneta: CONFIG_MVNETA off; needs kmod-phylink (C) |  |
| `kmod-mvpp2` | C | mvpp2: CONFIG_MVPP2 off; needs kmod-phylink (C) |  |
| `kmod-mwifiex-pcie` | C | mwifiex: CONFIG_MWIFIEX off; mwifiex_pcie: CONFIG_MWIFIEX_PCIE off; needs kmod-mac80211 (C) |  |
| `kmod-mwifiex-sdio` | C | mwifiex: CONFIG_MWIFIEX off; mwifiex_sdio: CONFIG_MWIFIEX_SDIO off; needs kmod-mac80211 (C) |  |
| `kmod-mwl8k` | C | mwl8k: CONFIG_MWL8K off; needs kmod-mac80211 (C) |  |
| `kmod-natsemi` | C | natsemi: CONFIG_NATSEMI off |  |
| `kmod-ne2k-pci` | C | 8390: CONFIG_APNE off; CONFIG_NE2K_PCI off; CONFIG_PCMCIA_AXNET off; CONFIG_PCMCIA_PCNET off; CONFIG_STNIC off; CONFIG_ULTRA off; CONFIG_WD80x3 off; ne2k-pci: CONFIG_NE2K_PCI off |  |
| `kmod-netconsole` | C | netconsole: CONFIG_NETCONSOLE also sets CONFIG_NETPOLL=y CONFIG_NET_POLL_CONTROLLER=y |  |
| `kmod-nf-flow` | C | nf_flow_table: CONFIG_NF_FLOW_TABLE off |  |
| `kmod-nf-ipvs-ftp` | C | ip_vs_ftp: CONFIG_IP_VS_FTP off; needs kmod-nf-ipvs (C) |  |
| `kmod-nf-ipvs-sip` | C | ip_vs_pe_sip: CONFIG_IP_VS_PE_SIP off; needs kmod-nf-ipvs (C); needs kmod-nf-nathelper-extra (C) |  |
| `kmod-nf-nathelper-extra` | C | nf_conntrack_broadcast: CONFIG_NF_CONNTRACK_BROADCAST off; nf_nat_amanda: CONFIG_NF_NAT_AMANDA off; nf_nat_h323: CONFIG_NF_NAT_H323 off; nf_nat_irc: CONFIG_NF_NAT_IRC off; nf_nat_pptp: CONFIG_NF_NAT_PPTP off; nf_nat_snmp_basic: CONFIG_NF_NAT_SNMP_BASIC off; needs kmod-asn1-decoder (C) |  |
| `kmod-nft-arp` | C | needs kmod-nft-core (C) |  |
| `kmod-nft-compat` | C | nft_compat: CONFIG_NFT_COMPAT off; needs kmod-nft-core (C) |  |
| `kmod-nft-connlimit` | C | nft_connlimit: CONFIG_NFT_CONNLIMIT off; needs kmod-nft-core (C) |  |
| `kmod-nft-dup-inet` | C | nft_dup_ipv4: CONFIG_NFT_DUP_IPV4 off; nft_dup_ipv6: CONFIG_NFT_DUP_IPV6 off; needs kmod-nft-core (C) |  |
| `kmod-nft-socket` | C | nft_socket: CONFIG_NFT_SOCKET off; needs kmod-nft-core (C) |  |
| `kmod-oid-registry` | C | oid_registry: CONFIG_OID_REGISTRY off |  |
| `kmod-openvswitch-geneve` | C | vport-geneve: CONFIG_OPENVSWITCH_GENEVE off; needs kmod-openvswitch (C) |  |
| `kmod-openvswitch-gre` | C | vport-gre: CONFIG_OPENVSWITCH_GRE off; needs kmod-openvswitch (C) |  |
| `kmod-openvswitch-vxlan` | C | vport-vxlan: CONFIG_OPENVSWITCH_VXLAN off; needs kmod-openvswitch (C) |  |
| `kmod-parport-pc` | C | needs kmod-ppdev (C) |  |
| `kmod-pcnet32` | C | pcnet32: CONFIG_PCNET32 off |  |
| `kmod-phy-broadcom` | C | needs kmod-phylib-broadcom (C) |  |
| `kmod-phylib-broadcom` | C | bcm-phy-lib: CONFIG_BCM_NET_PHYLIB off |  |
| `kmod-phylink` | C | phylink: CONFIG_PHYLINK off |  |
| `kmod-pinctrl-mcp23s08` | C | pinctrl-mcp23s08: CONFIG_PINCTRL_MCP23S08 also sets CONFIG_GPIOLIB_IRQCHIP=y |  |
| `kmod-pmbus-core` | C | pmbus_core: CONFIG_PMBUS off |  |
| `kmod-pmbus-zl6100` | C | zl6100: CONFIG_SENSORS_ZL6100 off; needs kmod-pmbus-core (C) |  |
| `kmod-ppdev` | C | ppdev: CONFIG_PPDEV off |  |
| `kmod-pps-gpio` | C | pps-gpio: CONFIG_PPS_CLIENT_GPIO off |  |
| `kmod-pps-ldisc` | C | pps-ldisc: CONFIG_PPS_CLIENT_LDISC off |  |
| `kmod-ptp` | C | ptp: CONFIG_PTP_1588_CLOCK off |  |
| `kmod-qlcnic` | C | qlcnic: CONFIG_QLCNIC also sets CONFIG_QLCNIC_SRIOV=y |  |
| `kmod-qrtr` | C | qrtr: CONFIG_QRTR off |  |
| `kmod-qrtr-tun` | C | qrtr-tun: CONFIG_QRTR_TUN off; needs kmod-qrtr (C) |  |
| `kmod-renesas-net-avb` | C | ravb: CONFIG_RAVB off; needs kmod-phylink (C); needs kmod-ptp (C) |  |
| `kmod-rsi91x` | C | rsi_91x: CONFIG_RSI_91X off; needs kmod-mac80211 (C) |  |
| `kmod-rsi91x-sdio` | C | rsi_sdio: CONFIG_RSI_SDIO off; needs kmod-mac80211 (C); needs kmod-rsi91x (C) |  |
| `kmod-rsi91x-usb` | C | rsi_usb: CONFIG_RSI_USB off; needs kmod-mac80211 (C); needs kmod-rsi91x (C) |  |
| `kmod-rt2800-lib` | C | rt2800lib: CONFIG_RT2800_LIB off; needs kmod-rt2x00-lib (C) |  |
| `kmod-rt2800-mmio` | C | rt2800mmio: CONFIG_RT2800_LIB_MMIO off; needs kmod-rt2800-lib (C); needs kmod-rt2x00-mmio (C) |  |
| `kmod-rt2800-pci` | C | rt2800pci: CONFIG_RT2800PCI off; needs kmod-rt2x00-pci (C); needs kmod-rt2800-lib (C); needs kmod-rt2800-mmio (C) |  |
| `kmod-rt2800-usb` | C | rt2800usb: CONFIG_RT2800USB off; needs kmod-rt2x00-usb (C); needs kmod-rt2800-lib (C) |  |
| `kmod-rt2x00-lib` | C | rt2x00lib: CONFIG_RT2X00_LIB off; needs kmod-mac80211 (C) |  |
| `kmod-rt2x00-mmio` | C | rt2x00mmio: CONFIG_RT2X00_LIB_MMIO off; needs kmod-rt2x00-lib (C) |  |
| `kmod-rt2x00-pci` | C | rt2x00pci: CONFIG_RT2X00_LIB_PCI off; needs kmod-rt2x00-mmio (C); needs kmod-rt2x00-lib (C) |  |
| `kmod-rt2x00-usb` | C | rt2x00usb: CONFIG_RT2X00_LIB_USB off; needs kmod-rt2x00-lib (C) |  |
| `kmod-rtl8192c-common` | C | rtl8192c-common: CONFIG_RTL8192C_COMMON off; needs kmod-rtlwifi (C) |  |
| `kmod-rtl8192ce` | C | rtl8192ce: CONFIG_RTL8192CE off; needs kmod-rtlwifi-pci (C); needs kmod-rtl8192c-common (C) |  |
| `kmod-rtl8192cu` | C | rtl8192cu: CONFIG_RTL8192CU off; needs kmod-rtlwifi-usb (C); needs kmod-rtl8192c-common (C) |  |
| `kmod-rtl8192de` | C | rtl8192de: CONFIG_RTL8192DE off; needs kmod-rtlwifi-pci (C) |  |
| `kmod-rtl8192se` | C | rtl8192se: CONFIG_RTL8192SE off; needs kmod-rtlwifi-pci (C) |  |
| `kmod-rtl8723bs` | C | r8723bs: CONFIG_RTL8723BS off; needs kmod-mac80211 (C) |  |
| `kmod-rtl8821ae` | C | rtl8821ae: CONFIG_RTL8821AE off; needs kmod-rtlwifi-btcoexist (C); needs kmod-rtlwifi-pci (C) |  |
| `kmod-rtl8xxxu` | C | rtl8xxxu: CONFIG_RTL8XXXU off; needs kmod-mac80211 (C) |  |
| `kmod-rtlwifi` | C | rtlwifi: CONFIG_RTLWIFI off; needs kmod-mac80211 (C) |  |
| `kmod-rtlwifi-btcoexist` | C | btcoexist: CONFIG_RTLBTCOEXIST off; needs kmod-rtlwifi (C) |  |
| `kmod-rtlwifi-pci` | C | rtl_pci: CONFIG_RTLWIFI_PCI off; needs kmod-rtlwifi (C) |  |
| `kmod-rtlwifi-usb` | C | rtl_usb: CONFIG_RTLWIFI_USB off; needs kmod-rtlwifi (C) |  |
| `kmod-scsi-cdrom` | C | needs kmod-cdrom (C) |  |
| `kmod-serial-8250-exar` | C | 8250_exar: CONFIG_SERIAL_8250_EXAR off |  |
| `kmod-sfc` | C | sfc: CONFIG_SFC off; needs kmod-mdio (C); needs kmod-ptp (C) |  |
| `kmod-sfc-falcon` | C | sfc-falcon: CONFIG_SFC_FALCON off; needs kmod-mdio (C) |  |
| `kmod-sfp` | C | mdio-i2c: CONFIG_MDIO_I2C off; sfp: CONFIG_SFP off; needs kmod-phylink (C) |  |
| `kmod-skge` | C | skge: CONFIG_SKGE off |  |
| `kmod-sky2` | C | sky2: CONFIG_SKY2 off |  |
| `kmod-sound-ens1371` | C | snd-ens1371: CONFIG_SND_ENS1371 also sets CONFIG_SND_VMASTER=y; needs kmod-ac97 (C) |  |
| `kmod-sound-i8x0` | C | snd-intel8x0: CONFIG_SND_INTEL8X0 also sets CONFIG_SND_VMASTER=y; needs kmod-ac97 (C) |  |
| `kmod-sound-mpu401` | C | snd-mpu401-uart: CONFIG_SND_MPU401_UART off |  |
| `kmod-sound-soc-ac97` | C | snd-soc-ac97: CONFIG_SND_SOC_AC97_CODEC also sets CONFIG_AC97_BUS=y CONFIG_SND_SOC_AC97_BUS=y CONFIG_SND_VMASTER=y; needs kmod-ac97 (C); needs kmod-sound-soc-core (C) |  |
| `kmod-sound-soc-core` | C | needs kmod-ac97 (C) |  |
| `kmod-sound-soc-spdif` | C | needs kmod-sound-soc-core (C) |  |
| `kmod-sound-via82xx` | C | snd-via82xx: CONFIG_SND_VIA82XX also sets CONFIG_SND_VMASTER=y; needs kmod-ac97 (C); needs kmod-sound-mpu401 (C) |  |
| `kmod-ssb` | C | ssb: CONFIG_SSB also sets CONFIG_SSB_B43_PCI_BRIDGE=y CONFIG_SSB_BLOCKIO=y CONFIG_SSB_DRIVER_PCICORE_POSSIBLE=y |  |
| `kmod-switch-bcm53xx-mdio` | C | b53_mdio: CONFIG_B53_MDIO_DRIVER off; CONFIG_SWCONFIG_B53_PHY_DRIVER off |  |
| `kmod-switch-rtl8366rb` | C | rtl8366rb: CONFIG_RTL8366RB_PHY off |  |
| `kmod-switch-rtl8366s` | C | rtl8366s: CONFIG_RTL8366S_PHY off |  |
| `kmod-switch-rtl8367` | C | rtl8367: CONFIG_RTL8367_PHY off |  |
| `kmod-switch-rtl8367b` | C | rtl8367b: CONFIG_RTL8367B_PHY off |  |
| `kmod-tg3` | C | tg3: CONFIG_TIGON3 off; needs kmod-ptp (C) |  |
| `kmod-thunderx-net` | C | nicpf: CONFIG_THUNDER_NIC_PF off; nicvf: CONFIG_THUNDER_NIC_VF off; thunder_bgx: CONFIG_THUNDER_NIC_BGX off; thunder_xcv: CONFIG_THUNDER_NIC_RGX off; needs kmod-phylink (C); needs kmod-mdio-thunder (C) |  |
| `kmod-tulip` | C | de2104x: CONFIG_DE2104X off; dmfe: CONFIG_DM9102 off; tulip: CONFIG_TULIP off; uli526x: CONFIG_ULI526X off; winbond-840: CONFIG_WINBOND_840 off |  |
| `kmod-usb-atm` | C | usbatm: CONFIG_USB_ATM off; needs kmod-atm (C) |  |
| `kmod-usb-atm-cxacru` | C | cxacru: CONFIG_USB_CXACRU off; needs kmod-usb-atm (C) |  |
| `kmod-usb-atm-speedtouch` | C | speedtch: CONFIG_USB_SPEEDTOUCH off; needs kmod-usb-atm (C) |  |
| `kmod-usb-atm-ueagle` | C | ueagle-atm: CONFIG_USB_UEAGLEATM off; needs kmod-usb-atm (C) |  |
| `kmod-usb-dwc2` | C | dwc2: CONFIG_USB_DWC2 also sets CONFIG_USB_DWC2_DUAL_ROLE=y |  |
| `kmod-usb-dwc2-pci` | C | dwc2_pci: CONFIG_USB_DWC2_PCI off; needs kmod-usb-dwc2 (C); needs kmod-usb-phy-nop (C) |  |
| `kmod-usb-ehci` | C | ehci-hcd: CONFIG_USB_EHCI_HCD also sets CONFIG_USB_EHCI_TT_NEWSCHED=y |  |
| `kmod-usb-hid-cp2112` | C | hid-cp2112: CONFIG_HID_CP2112 off |  |
| `kmod-usb-net` | C | usbnet: CONFIG_USB_USBNET off |  |
| `kmod-usb-net-asix` | C | asix: CONFIG_USB_NET_AX8817X off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-asix-ax88179` | C | ax88179_178a: CONFIG_USB_NET_AX88179_178A off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-cdc-eem` | C | cdc_eem: CONFIG_USB_NET_CDC_EEM off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-cdc-ether` | C | cdc_ether: CONFIG_USB_NET_CDCETHER off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-cdc-mbim` | C | cdc_mbim: CONFIG_USB_NET_CDC_MBIM off; needs kmod-usb-net (C); needs kmod-usb-net-cdc-ncm (C) |  |
| `kmod-usb-net-cdc-ncm` | C | cdc_ncm: CONFIG_USB_NET_CDC_NCM off; needs kmod-usb-net (C); needs kmod-usb-net-cdc-ether (C) |  |
| `kmod-usb-net-cdc-subset` | C | cdc_subset: CONFIG_USB_NET_CDC_SUBSET_ENABLE off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-dm9601-ether` | C | dm9601: CONFIG_USB_NET_DM9601 off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-hso` | C | hso: CONFIG_USB_HSO off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-huawei-cdc-ncm` | C | huawei_cdc_ncm: CONFIG_USB_NET_HUAWEI_CDC_NCM off; needs kmod-usb-net (C); needs kmod-usb-net-cdc-ncm (C) |  |
| `kmod-usb-net-ipheth` | C | ipheth: CONFIG_USB_IPHETH off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-kalmia` | C | kalmia: CONFIG_USB_NET_KALMIA off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-kaweth` | C | kaweth: CONFIG_USB_KAWETH off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-lan78xx` | C | lan78xx: CONFIG_USB_LAN78XX off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-mcs7830` | C | mcs7830: CONFIG_USB_NET_MCS7830 off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-pegasus` | C | pegasus: CONFIG_USB_PEGASUS off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-pl` | C | plusb: CONFIG_USB_NET_PLUSB off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-qmi-wwan` | C | qmi_wwan: CONFIG_USB_NET_QMI_WWAN off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-rndis` | C | rndis_host: CONFIG_USB_NET_RNDIS_HOST off; needs kmod-usb-net (C); needs kmod-usb-net-cdc-ether (C) |  |
| `kmod-usb-net-rtl8150` | C | rtl8150: CONFIG_USB_RTL8150 off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-sierrawireless` | C | sierra_net: CONFIG_USB_SIERRA_NET off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-smsc75xx` | C | smsc75xx: CONFIG_USB_NET_SMSC75XX off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-smsc95xx` | C | smsc95xx: CONFIG_USB_NET_SMSC95XX off; needs kmod-usb-net (C) |  |
| `kmod-usb-net-sr9700` | C | sr9700: CONFIG_USB_NET_SR9700 off; needs kmod-usb-net (C) |  |
| `kmod-usb-ohci` | C | ohci-platform: CONFIG_USB_OHCI_HCD_PLATFORM off |  |
| `kmod-usb-ohci-pci` | C | ohci-pci: CONFIG_USB_OHCI_HCD_PCI off; needs kmod-usb-ohci (C) |  |
| `kmod-usb-phy-nop` | C | phy-generic: CONFIG_NOP_USB_XCEIV also sets CONFIG_USB_PHY=y |  |
| `kmod-usb-serial-ark3116` | C | ark3116: CONFIG_USB_SERIAL_ARK3116 off |  |
| `kmod-usb-serial-belkin` | C | belkin_sa: CONFIG_USB_SERIAL_BELKIN off |  |
| `kmod-usb-serial-cp210x` | C | cp210x: CONFIG_USB_SERIAL_CP210X off |  |
| `kmod-usb-serial-cypress-m8` | C | cypress_m8: CONFIG_USB_SERIAL_CYPRESS_M8 off |  |
| `kmod-usb-serial-edgeport` | C | io_edgeport: CONFIG_USB_SERIAL_EDGEPORT off |  |
| `kmod-usb-serial-garmin` | C | garmin_gps: CONFIG_USB_SERIAL_GARMIN off |  |
| `kmod-usb-serial-ipw` | C | ipw: CONFIG_USB_SERIAL_IPW off; needs kmod-usb-serial-wwan (C) |  |
| `kmod-usb-serial-keyspan` | C | keyspan: CONFIG_USB_SERIAL_KEYSPAN off |  |
| `kmod-usb-serial-mct` | C | mct_u232: CONFIG_USB_SERIAL_MCT_U232 off |  |
| `kmod-usb-serial-mos7720` | C | mos7720: CONFIG_USB_SERIAL_MOS7720 off |  |
| `kmod-usb-serial-mos7840` | C | mos7840: CONFIG_USB_SERIAL_MOS7840 off |  |
| `kmod-usb-serial-option` | C | option: CONFIG_USB_SERIAL_OPTION off; needs kmod-usb-serial-wwan (C) |  |
| `kmod-usb-serial-oti6858` | C | oti6858: CONFIG_USB_SERIAL_OTI6858 off |  |
| `kmod-usb-serial-pl2303` | C | pl2303: CONFIG_USB_SERIAL_PL2303 off |  |
| `kmod-usb-serial-qualcomm` | C | qcserial: CONFIG_USB_SERIAL_QUALCOMM off; needs kmod-usb-serial-wwan (C) |  |
| `kmod-usb-serial-sierrawireless` | C | sierra: CONFIG_USB_SERIAL_SIERRAWIRELESS off |  |
| `kmod-usb-serial-simple` | C | usb-serial-simple: CONFIG_USB_SERIAL_SIMPLE off |  |
| `kmod-usb-serial-ti-usb` | C | ti_usb_3410_5052: CONFIG_USB_SERIAL_TI off |  |
| `kmod-usb-serial-visor` | C | visor: CONFIG_USB_SERIAL_VISOR off |  |
| `kmod-usb-serial-wwan` | C | usb_wwan: CONFIG_USB_SERIAL_WWAN off |  |
| `kmod-usb-uhci` | C | uhci-hcd: CONFIG_USB_UHCI_HCD off |  |
| `kmod-usb2` | C | ehci-fsl: CONFIG_USB_EHCI_FSL off; ehci-orion: CONFIG_USB_EHCI_HCD_ORION off; ehci-platform: CONFIG_USB_EHCI_HCD_PLATFORM off; fsl-mph-dr-of: CONFIG_USB_EHCI_FSL off; CONFIG_USB_FSL_USB2 off; needs kmod-usb-ehci (C) |  |
| `kmod-usb2-pci` | C | ehci-pci: CONFIG_USB_EHCI_PCI off; needs kmod-usb2 (C) |  |
| `kmod-via-rhine` | C | via-rhine: CONFIG_VIA_RHINE off |  |
| `kmod-via-velocity` | C | via-velocity: CONFIG_VIA_VELOCITY off |  |
| `kmod-video-gspca-conex` | C | gspca_conex: CONFIG_USB_GSPCA_CONEX off |  |
| `kmod-video-gspca-etoms` | C | gspca_etoms: CONFIG_USB_GSPCA_ETOMS off |  |
| `kmod-video-gspca-finepix` | C | gspca_finepix: CONFIG_USB_GSPCA_FINEPIX off |  |
| `kmod-video-gspca-gl860` | C | gspca_gl860: CONFIG_USB_GL860 off |  |
| `kmod-video-gspca-jeilinj` | C | gspca_jeilinj: CONFIG_USB_GSPCA_JEILINJ off |  |
| `kmod-video-gspca-konica` | C | gspca_konica: CONFIG_USB_GSPCA_KONICA off |  |
| `kmod-video-gspca-m5602` | C | gspca_m5602: CONFIG_USB_M5602 off |  |
| `kmod-video-gspca-mars` | C | gspca_mars: CONFIG_USB_GSPCA_MARS off |  |
| `kmod-video-gspca-mr97310a` | C | gspca_mr97310a: CONFIG_USB_GSPCA_MR97310A off |  |
| `kmod-video-gspca-ov519` | C | gspca_ov519: CONFIG_USB_GSPCA_OV519 off |  |
| `kmod-video-gspca-ov534` | C | gspca_ov534: CONFIG_USB_GSPCA_OV534 off |  |
| `kmod-video-gspca-ov534-9` | C | gspca_ov534_9: CONFIG_USB_GSPCA_OV534_9 off |  |
| `kmod-video-gspca-pac207` | C | gspca_pac207: CONFIG_USB_GSPCA_PAC207 off |  |
| `kmod-video-gspca-pac7311` | C | gspca_pac7311: CONFIG_USB_GSPCA_PAC7311 off |  |
| `kmod-video-gspca-se401` | C | gspca_se401: CONFIG_USB_GSPCA_SE401 off |  |
| `kmod-video-gspca-sn9c20x` | C | gspca_sn9c20x: CONFIG_USB_GSPCA_SN9C20X off |  |
| `kmod-video-gspca-sonixb` | C | gspca_sonixb: CONFIG_USB_GSPCA_SONIXB off |  |
| `kmod-video-gspca-sonixj` | C | gspca_sonixj: CONFIG_USB_GSPCA_SONIXJ off |  |
| `kmod-video-gspca-spca500` | C | gspca_spca500: CONFIG_USB_GSPCA_SPCA500 off |  |
| `kmod-video-gspca-spca501` | C | gspca_spca501: CONFIG_USB_GSPCA_SPCA501 off |  |
| `kmod-video-gspca-spca505` | C | gspca_spca505: CONFIG_USB_GSPCA_SPCA505 off |  |
| `kmod-video-gspca-spca506` | C | gspca_spca506: CONFIG_USB_GSPCA_SPCA506 off |  |
| `kmod-video-gspca-spca508` | C | gspca_spca508: CONFIG_USB_GSPCA_SPCA508 off |  |
| `kmod-video-gspca-spca561` | C | gspca_spca561: CONFIG_USB_GSPCA_SPCA561 off |  |
| `kmod-video-gspca-sq905` | C | gspca_sq905: CONFIG_USB_GSPCA_SQ905 off |  |
| `kmod-video-gspca-sq905c` | C | gspca_sq905c: CONFIG_USB_GSPCA_SQ905C off |  |
| `kmod-video-gspca-sq930x` | C | gspca_sq930x: CONFIG_USB_GSPCA_SQ930X off |  |
| `kmod-video-gspca-stk014` | C | gspca_stk014: CONFIG_USB_GSPCA_STK014 off |  |
| `kmod-video-gspca-stv06xx` | C | gspca_stv06xx: CONFIG_USB_STV06XX off |  |
| `kmod-video-gspca-sunplus` | C | gspca_sunplus: CONFIG_USB_GSPCA_SUNPLUS off |  |
| `kmod-video-gspca-t613` | C | gspca_t613: CONFIG_USB_GSPCA_T613 off |  |
| `kmod-video-gspca-tv8532` | C | gspca_tv8532: CONFIG_USB_GSPCA_TV8532 off |  |
| `kmod-video-gspca-vc032x` | C | gspca_vc032x: CONFIG_USB_GSPCA_VC032X off |  |
| `kmod-video-gspca-zc3xx` | C | gspca_zc3xx: CONFIG_USB_GSPCA_ZC3XX off |  |
| `kmod-video-pwc` | C | pwc: CONFIG_USB_PWC also sets CONFIG_USB_PWC_INPUT_EVDEV=y |  |
| `kmod-w1-master-ds2482` | C | ds2482: CONFIG_W1_MASTER_DS2482 off |  |
| `kmod-w1-master-ds2490` | C | ds2490: CONFIG_W1_MASTER_DS2490 off |  |
| `kmod-w1-master-gpio` | C | w1-gpio: CONFIG_W1_MASTER_GPIO off |  |
| `kmod-w1-slave-ds2413` | C | w1_ds2413: CONFIG_W1_SLAVE_DS2413 off |  |
| `kmod-w1-slave-ds2431` | C | w1_ds2431: CONFIG_W1_SLAVE_DS2431 off |  |
| `kmod-w1-slave-ds2433` | C | w1_ds2433: CONFIG_W1_SLAVE_DS2433 off |  |
| `kmod-w1-slave-smem` | C | w1_smem: CONFIG_W1_SLAVE_SMEM off |  |
| `kmod-w1-slave-therm` | C | w1_therm: CONFIG_W1_SLAVE_THERM off |  |
| `kmod-wil6210` | C | wil6210: CONFIG_WIL6210 off; needs kmod-mac80211 (C) |  |
| `kmod-wl12xx` | C | wl12xx: CONFIG_WL12XX off; needs kmod-wlcore (C) |  |
| `kmod-wl18xx` | C | wl18xx: CONFIG_WL18XX off; needs kmod-wlcore (C) |  |
| `kmod-wlcore` | C | wlcore: CONFIG_WLCORE off; wlcore_sdio: CONFIG_WLCORE_SDIO off; needs kmod-mac80211 (C) |  |
| `kmod-bluetooth` | D | btintel: CONFIG_BT_INTEL off; btrtl: CONFIG_BT_RTL off; btusb: CONFIG_BT_HCIBTUSB also sets CONFIG_BT_HCIBTUSB_BCM=y CONFIG_BT_HCIBTUSB_RTL=y; needs kmod-crypto-ecdh (D) | bluelog, bluelog-live, bluez-libs |
| `kmod-macremapper` | D | macremapper: no 4.19 source; needs kmod-cfg80211 (C) | dcwapd, libdcwproto, mrmctl |
| `kmod-dm` | D | dm-crypt: CONFIG_DM_CRYPT off; dm-log: CONFIG_DM_MIRROR off; dm-mirror: CONFIG_DM_MIRROR off; dm-mod: CONFIG_BLK_DEV_DM off; dm-region-hash: CONFIG_DM_MIRROR off; needs kmod-keys-encrypted (D) | libdevmapper, libdevmapper-selinux |
| `kmod-fs-cifs` | D | cifs: CONFIG_CIFS also sets CONFIG_CIFS_ALLOW_INSECURE_LEGACY=y CONFIG_CIFS_DEBUG=y; needs kmod-fs-smbfs-common (D); needs kmod-crypto-sha256 (D); needs kmod-crypto-des (D); needs kmod-asn1-decoder (C); needs kmod-oid-registry (C) | cifsmount, smbinfo |
| `kmod-ip-vti` | D | needs kmod-ipsec4 (D) | libreswan, vti |
| `kmod-ip6-vti` | D | needs kmod-ipsec6 (D) | libreswan, vti |
| `kmod-ipsec` | D | needs kmod-crypto-des (D) | libreswan, strongswan |
| `kmod-ipsec4` | D | needs kmod-ipsec (D) | libreswan, strongswan |
| `kmod-ipsec6` | D | needs kmod-ipsec (D) | libreswan, strongswan |
| `kmod-nft-bridge` | D | nf_conntrack_bridge: no 4.19 source; nft_meta_bridge: no 4.19 source; nft_reject_bridge: CONFIG_NFT_BRIDGE_REJECT off; needs kmod-nft-core (C) | nft-qos, phantap |
| `kmod-nft-nat` | D | nft_chain_nat: no 4.19 source; nft_masq: CONFIG_NFT_MASQ off; nft_nat: CONFIG_NFT_NAT off; needs kmod-nft-core (C) | firewall4, pbr |
| `kmod-xfrm-interface` | D | needs kmod-ipsec4 (D); needs kmod-ipsec6 (D) | libreswan, xfrm |
| `kmod-crypto-des` | D | libdes: no 4.19 source | strongswan |
| `kmod-fs-btrfs` | D | needs kmod-lib-lzo (D); needs kmod-lib-raid6 (C); needs kmod-lib-xor (C); needs kmod-lib-zstd (C); needs kmod-crypto-blake2b (D); needs kmod-crypto-xxhash (D) | btrfs-progs |
| `kmod-fs-ksmbd` | D | ksmbd: no 4.19 source; needs kmod-crypto-des (D); needs kmod-crypto-sha256 (D); needs kmod-asn1-decoder (C); needs kmod-oid-registry (C); needs kmod-fs-smbfs-common (D) | ksmbd-server |
| `kmod-fs-nfsd` | D | nfsd: CONFIG_NFSD also sets CONFIG_NFS_COMMON=y; needs kmod-fs-nfs-common (C); needs kmod-fs-nfs-common-rpcsec (D) | nfs-kernel-server |
| `kmod-ipt-account` | D | xt_ACCOUNT: no 4.19 source; needs kmod-ipt-compat-xtables (D) | iptables-mod-account |
| `kmod-ipt-chaos` | D | xt_CHAOS: no 4.19 source; needs kmod-ipt-compat-xtables (D); needs kmod-ipt-delude (D); needs kmod-ipt-tarpit (D) | iptables-mod-chaos |
| `kmod-ipt-condition` | D | xt_condition: no 4.19 source | iptables-mod-condition |
| `kmod-ipt-delude` | D | xt_DELUDE: no 4.19 source; needs kmod-ipt-compat-xtables (D) | iptables-mod-delude |
| `kmod-ipt-dhcpmac` | D | xt_DHCPMAC: no 4.19 source; needs kmod-ipt-compat-xtables (D) | iptables-mod-dhcpmac |
| `kmod-ipt-dnetmap` | D | xt_DNETMAP: no 4.19 source; needs kmod-ipt-compat-xtables (D) | iptables-mod-dnetmap |
| `kmod-ipt-fuzzy` | D | xt_fuzzy: no 4.19 source | iptables-mod-fuzzy |
| `kmod-ipt-geoip` | D | xt_geoip: no 4.19 source | iptables-mod-geoip |
| `kmod-ipt-iface` | D | xt_iface: no 4.19 source | iptables-mod-iface |
| `kmod-ipt-ipmark` | D | xt_IPMARK: no 4.19 source; needs kmod-ipt-compat-xtables (D) | iptables-mod-ipmark |
| `kmod-ipt-ipp2p` | D | xt_ipp2p: no 4.19 source; needs kmod-ipt-compat-xtables (D) | iptables-mod-ipp2p |
| `kmod-ipt-ipv4options` | D | xt_ipv4options: no 4.19 source | iptables-mod-ipv4options |
| `kmod-ipt-length2` | D | xt_length2: no 4.19 source; needs kmod-ipt-compat-xtables (D) | iptables-mod-length2 |
| `kmod-ipt-logmark` | D | xt_LOGMARK: no 4.19 source; needs kmod-ipt-compat-xtables (D) | iptables-mod-logmark |
| `kmod-ipt-lscan` | D | xt_lscan: no 4.19 source | iptables-mod-lscan |
| `kmod-ipt-lua` | D | xt_LUA: no 4.19 source | iptables-mod-lua |
| `kmod-ipt-proto` | D | xt_PROTO: no 4.19 source | iptables-mod-proto |
| `kmod-ipt-psd` | D | xt_psd: no 4.19 source | iptables-mod-psd |
| `kmod-ipt-sysrq` | D | xt_SYSRQ: no 4.19 source; needs kmod-ipt-compat-xtables (D) | iptables-mod-sysrq |
| `kmod-ipt-tarpit` | D | xt_TARPIT: no 4.19 source; needs kmod-ipt-compat-xtables (D) | iptables-mod-tarpit |
| `kmod-jool-netfilter` | D | jool: no 4.19 source; jool_common: no 4.19 source; jool_siit: no 4.19 source | jool-tools-netfilter |
| `kmod-mdio-netlink` | D | mdio-netlink: no 4.19 source | mdio-tools |
| `kmod-netatop` | D | netatop: no 4.19 source | netatop |
| `kmod-nft-offload` | D | nf_flow_table_inet: CONFIG_NF_FLOW_TABLE_INET off; nf_flow_table_ipv4: CONFIG_NF_FLOW_TABLE_IPV4 off; nf_flow_table_ipv6: CONFIG_NF_FLOW_TABLE_IPV6 off; nft_flow_offload: CONFIG_NFT_FLOW_OFFLOAD off; needs kmod-nf-flow (C); needs kmod-nft-nat (D) | firewall4 |
| `kmod-pf-ring` | D | pf_ring: no 4.19 source | libpfring |
| `kmod-siit` | D | siit: no 4.19 source | luci-app-siitwizard |
| `kmod-asn1-encoder` | D | asn1_encoder: no 4.19 source |  |
| `kmod-ath11k` | D | ath11k: no 4.19 source; qmi_helpers: CONFIG_QCOM_QMI_HELPERS off; needs kmod-ath (C) |  |
| `kmod-ath11k-pci` | D | ath11k_pci: no 4.19 source; needs kmod-qrtr-mhi (D); needs kmod-ath11k (D) |  |
| `kmod-ath3k` | D | ath3k: CONFIG_BT_ATH3K off; needs kmod-bluetooth (D) |  |
| `kmod-bluetooth-6lowpan` | D | bluetooth_6lowpan: CONFIG_BT_6LOWPAN off; needs kmod-bluetooth (D) |  |
| `kmod-btmrvl` | D | btmrvl_sdio: CONFIG_BT_MRVL_SDIO off; needs kmod-bluetooth (D) |  |
| `kmod-btsdio` | D | needs kmod-bluetooth (D) |  |
| `kmod-button-hotplug` | D | button-hotplug: no 4.19 source |  |
| `kmod-crypto-blake2b` | D | blake2b_generic: no 4.19 source |  |
| `kmod-crypto-ecdh` | D | ecc: no 4.19 source |  |
| `kmod-crypto-essiv` | D | essiv: no 4.19 source |  |
| `kmod-crypto-hw-hifn-795x` | D | needs kmod-crypto-des (D) |  |
| `kmod-crypto-sha256` | D | libsha256: no 4.19 source |  |
| `kmod-crypto-xxhash` | D | xxhash_generic: no 4.19 source |  |
| `kmod-dahdi` | D | dahdi: no 4.19 source |  |
| `kmod-dahdi-dummy` | D | dahdi_dummy: no 4.19 source; needs kmod-dahdi (D) |  |
| `kmod-dahdi-echocan-oslec` | D | dahdi_echocan_oslec: no 4.19 source; needs kmod-dahdi (D) |  |
| `kmod-dahdi-hfcs` | D | dahdi_hfcs: no 4.19 source; needs kmod-dahdi (D) |  |
| `kmod-dm-raid` | D | dm-raid: CONFIG_DM_RAID off; needs kmod-dm (D); needs kmod-md-mod (C); needs kmod-md-raid0 (C); needs kmod-md-raid1 (C); needs kmod-md-raid10 (C); needs kmod-md-raid456 (C) |  |
| `kmod-dwmac-imx` | D | dwmac-imx: no 4.19 source; needs kmod-stmmac-core (D) |  |
| `kmod-dwmac-rockchip` | D | dwmac-rk: CONFIG_DWMAC_ROCKCHIP off; needs kmod-stmmac-core (D) |  |
| `kmod-dwmac-sun8i` | D | dwmac-sun8i: CONFIG_DWMAC_SUN8I off; needs kmod-stmmac-core (D) |  |
| `kmod-fs-exfat` | D | exfat: no 4.19 source |  |
| `kmod-fs-fscache` | D | cachefiles: CONFIG_CACHEFILES off; needs kmod-fs-netfs (D) |  |
| `kmod-fs-netfs` | D | netfs: no 4.19 source |  |
| `kmod-fs-nfs-common-rpcsec` | D | auth_rpcgss: CONFIG_SUNRPC_GSS off; rpcsec_gss_krb5: CONFIG_RPCSEC_GSS_KRB5 off; needs kmod-fs-nfs-common (C); needs kmod-crypto-des (D) |  |
| `kmod-fs-ntfs3` | D | ntfs3: no 4.19 source |  |
| `kmod-fs-smbfs-common` | D | cifs_arc4: no 4.19 source; cifs_md4: no 4.19 source |  |
| `kmod-fsl-dpaa2-console` | D | dpaa2-console: no 4.19 source |  |
| `kmod-fsl-dpaa2-net` | D | fsl-dpaa2-eth: CONFIG_FSL_DPAA2_ETH off; needs kmod-fsl-xgmac-mdio (C); needs kmod-phylink (C); needs kmod-fsl-pcs-lynx (D); needs kmod-fsl-mc-dpio (C) |  |
| `kmod-fsl-enetc-net` | D | fsl-enetc: no 4.19 source; fsl-enetc-ierb: no 4.19 source; fsl-enetc-mdio: no 4.19 source; fsl-enetc-vf: no 4.19 source; needs kmod-phylink (C); needs kmod-fsl-pcs-lynx (D) |  |
| `kmod-fsl-pcs-lynx` | D | pcs-lynx: no 4.19 source; needs kmod-phylink (C) |  |
| `kmod-gpio-button-hotplug` | D | gpio-button-hotplug: no 4.19 source |  |
| `kmod-gpio-cascade` | D | gpio-cascade: no 4.19 source; needs kmod-mux-core (C) |  |
| `kmod-hwmon-drivetemp` | D | drivetemp: no 4.19 source |  |
| `kmod-hwmon-gsc` | D | gateworks-gsc: no 4.19 source; gsc-hwmon: no 4.19 source |  |
| `kmod-hwmon-tps23861` | D | tps23861: no 4.19 source |  |
| `kmod-iavf` | D | iavf: no 4.19 source |  |
| `kmod-igc` | D | igc: no 4.19 source; needs kmod-ptp (C) |  |
| `kmod-iio-fxas21002c` | D | fxas21002c_core: no 4.19 source; needs kmod-industrialio-triggered-buffer (C) |  |
| `kmod-iio-fxas21002c-i2c` | D | fxas21002c_i2c: no 4.19 source; needs kmod-iio-fxas21002c (D) |  |
| `kmod-iio-fxas21002c-spi` | D | fxas21002c_spi: no 4.19 source; needs kmod-iio-fxas21002c (D) |  |
| `kmod-iio-fxos8700` | D | fxos8700_core: no 4.19 source |  |
| `kmod-iio-fxos8700-i2c` | D | fxos8700_i2c: no 4.19 source; needs kmod-iio-fxos8700 (D) |  |
| `kmod-iio-fxos8700-spi` | D | fxos8700_spi: no 4.19 source; needs kmod-iio-fxos8700 (D) |  |
| `kmod-iio-sps30` | D | sps30: no 4.19 source; sps30_i2c: no 4.19 source; needs kmod-industrialio-triggered-buffer (C) |  |
| `kmod-ipt-compat-xtables` | D | compat_xtables: no 4.19 source |  |
| `kmod-ipt-coova` | D | xt_coova: no 4.19 source |  |
| `kmod-ipt-nathelper-rtsp` | D | nf_conntrack_rtsp: no 4.19 source; nf_nat_rtsp: no 4.19 source |  |
| `kmod-ipt-rtpengine` | D | xt_RTPENGINE: no 4.19 source |  |
| `kmod-keys-encrypted` | D | needs kmod-crypto-sha256 (D); needs kmod-keys-trusted (D) |  |
| `kmod-keys-trusted` | D | needs kmod-tpm (D) |  |
| `kmod-ledtrig-audio` | D | ledtrig-audio: no 4.19 source |  |
| `kmod-ledtrig-pattern` | D | ledtrig-pattern: no 4.19 source |  |
| `kmod-ledtrig-tty` | D | ledtrig-tty: no 4.19 source |  |
| `kmod-lib-lzo` | D | lzo-rle: no 4.19 source |  |
| `kmod-mhi-bus` | D | mhi: no 4.19 source |  |
| `kmod-mhi-net` | D | mhi_net: no 4.19 source; needs kmod-mhi-bus (D) |  |
| `kmod-mhi-pci-generic` | D | mhi_pci_generic: no 4.19 source; needs kmod-mhi-bus (D) |  |
| `kmod-mhi-wwan-ctrl` | D | mhi_wwan_ctrl: no 4.19 source; needs kmod-mhi-bus (D); needs kmod-wwan (D) |  |
| `kmod-mhi-wwan-mbim` | D | mhi_wwan_mbim: no 4.19 source; needs kmod-mhi-bus (D); needs kmod-wwan (D) |  |
| `kmod-mt76` | D | needs kmod-mt76-core (C); needs kmod-mt76x2 (D); needs kmod-mt7603 (D) |  |
| `kmod-mt76-connac` | D | mt76-connac-lib: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt76-core (C) |  |
| `kmod-mt76-sdio` | D | mt76-sdio: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt76-core (C) |  |
| `kmod-mt7603` | D | mt7603e: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt76-core (C) |  |
| `kmod-mt7615-common` | D | mt7615-common: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt76-core (C); needs kmod-mt76-connac (D) |  |
| `kmod-mt7615-firmware` | D | needs kmod-mac80211 (C); needs kmod-mt7615e (D) |  |
| `kmod-mt7615e` | D | mt7615e: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt7615-common (D) |  |
| `kmod-mt7622-firmware` | D | needs kmod-mac80211 (C); needs kmod-mt7615e (D) |  |
| `kmod-mt7663-usb-sdio` | D | mt7663-usb-sdio-common: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt7615-common (D) |  |
| `kmod-mt7663s` | D | mt7663s: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt76-sdio (D); needs kmod-mt7615-common (D); needs kmod-mt7663-usb-sdio (D) |  |
| `kmod-mt7663u` | D | mt7663u: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt76-usb (C); needs kmod-mt7615-common (D); needs kmod-mt7663-usb-sdio (D) |  |
| `kmod-mt76x0-common` | D | mt76x0-common: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt76x02-common (D) |  |
| `kmod-mt76x02-common` | D | mt76x02-lib: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt76-core (C) |  |
| `kmod-mt76x02-usb` | D | mt76x02-usb: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt76-usb (C); needs kmod-mt76x02-common (D) |  |
| `kmod-mt76x0e` | D | mt76x0e: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt76x0-common (D) |  |
| `kmod-mt76x0u` | D | mt76x0u: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt76x0-common (D); needs kmod-mt76x02-usb (D) |  |
| `kmod-mt76x2` | D | mt76x2e: CONFIG_MT76x2E off; needs kmod-mac80211 (C); needs kmod-mt76x2-common (D) |  |
| `kmod-mt76x2-common` | D | mt76x2-common: CONFIG_MT76x2_COMMON off; needs kmod-mac80211 (C); needs kmod-mt76-core (C); needs kmod-mt76x02-common (D) |  |
| `kmod-mt76x2u` | D | mt76x2u: CONFIG_MT76x2U off; needs kmod-mac80211 (C); needs kmod-mt76x2-common (D); needs kmod-mt76x02-usb (D) |  |
| `kmod-mt7915-firmware` | D | needs kmod-mac80211 (C); needs kmod-mt7915e (D) |  |
| `kmod-mt7915e` | D | mt7915e: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt76-connac (D) |  |
| `kmod-mt7916-firmware` | D | needs kmod-mac80211 (C); needs kmod-mt7915e (D) |  |
| `kmod-mt7921-common` | D | mt7921-common: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt792x-common (D); needs kmod-mt7921-firmware (C) |  |
| `kmod-mt7921e` | D | mt7921e: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt7921-common (D) |  |
| `kmod-mt7921s` | D | mt7921s: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt76-sdio (D); needs kmod-mt7921-common (D) |  |
| `kmod-mt7921u` | D | mt7921u: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt792x-usb (D); needs kmod-mt7921-common (D) |  |
| `kmod-mt7925-common` | D | mt7925-common: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt792x-common (D) |  |
| `kmod-mt7925e` | D | mt7925e: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt7925-common (D) |  |
| `kmod-mt7925u` | D | mt7925u: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt792x-usb (D); needs kmod-mt7925-common (D) |  |
| `kmod-mt792x-common` | D | mt792x-lib: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt76-connac (D) |  |
| `kmod-mt792x-usb` | D | mt792x-usb: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt792x-common (D); needs kmod-mt76-usb (C) |  |
| `kmod-mt7996-firmware` | D | needs kmod-mac80211 (C); needs kmod-mt7996e (D) |  |
| `kmod-mt7996e` | D | mt7996e: no 4.19 source; needs kmod-mac80211 (C); needs kmod-mt76-connac (D) |  |
| `kmod-mtd-rw` | D | mtd-rw: no 4.19 source |  |
| `kmod-mtdtests` | D | mtd_test: no 4.19 source |  |
| `kmod-nft-xfrm` | D | nft_xfrm: no 4.19 source; needs kmod-nft-core (C) |  |
| `kmod-octeontx2-net` | D | rvu_af: no 4.19 source; rvu_mbox: no 4.19 source; rvu_nicpf: no 4.19 source; rvu_nicvf: no 4.19 source; needs kmod-phylink (C); needs kmod-ptp (C) |  |
| `kmod-ovpn-dco` | D | ovpn-dco: no 4.19 source |  |
| `kmod-owl-loader` | D | ath9k_pci_owl_loader: no 4.19 source; needs kmod-ath9k (C) |  |
| `kmod-pcs-xpcs` | D | pcs_xpcs: no 4.19 source |  |
| `kmod-pinctrl-mcp23s08-i2c` | D | pinctrl-mcp23s08_i2c: no 4.19 source; needs kmod-pinctrl-mcp23s08 (C) |  |
| `kmod-pinctrl-mcp23s08-spi` | D | pinctrl-mcp23s08_spi: no 4.19 source; needs kmod-pinctrl-mcp23s08 (C) |  |
| `kmod-qrtr-mhi` | D | qrtr-mhi: no 4.19 source; needs kmod-mhi-bus (D); needs kmod-qrtr (C) |  |
| `kmod-r8101` | D | r8101: no 4.19 source |  |
| `kmod-r8125` | D | r8125: no 4.19 source |  |
| `kmod-r8125-rss` | D | r8125: no 4.19 source |  |
| `kmod-r8126` | D | r8126: no 4.19 source |  |
| `kmod-r8126-rss` | D | r8126: no 4.19 source |  |
| `kmod-r8168` | D | r8168: no 4.19 source |  |
| `kmod-rtl8812au-ct` | D | rtl8812au: no 4.19 source; needs kmod-cfg80211 (C) |  |
| `kmod-rtw88` | D | rtw88_8723d: no 4.19 source; rtw88_8723de: no 4.19 source; rtw88_8822b: no 4.19 source; rtw88_8822be: no 4.19 source; rtw88_8822c: no 4.19 source; rtw88_8822ce: no 4.19 source; rtw88_core: no 4.19 source; rtw88_pci: no 4.19 source; needs kmod-mac80211 (C) |  |
| `kmod-sched-fq-pie` | D | sch_fq_pie: no 4.19 source |  |
| `kmod-sound-hda-codec-analog` | D | needs kmod-sound-hda-core (D) |  |
| `kmod-sound-hda-codec-ca0110` | D | needs kmod-sound-hda-core (D) |  |
| `kmod-sound-hda-codec-ca0132` | D | needs kmod-sound-hda-core (D) |  |
| `kmod-sound-hda-codec-cirrus` | D | needs kmod-sound-hda-core (D) |  |
| `kmod-sound-hda-codec-cmedia` | D | needs kmod-sound-hda-core (D) |  |
| `kmod-sound-hda-codec-conexant` | D | needs kmod-sound-hda-core (D) |  |
| `kmod-sound-hda-codec-hdmi` | D | needs kmod-sound-hda-core (D) |  |
| `kmod-sound-hda-codec-idt` | D | needs kmod-sound-hda-core (D) |  |
| `kmod-sound-hda-codec-realtek` | D | needs kmod-sound-hda-core (D) |  |
| `kmod-sound-hda-codec-si3054` | D | needs kmod-sound-hda-core (D) |  |
| `kmod-sound-hda-codec-via` | D | needs kmod-sound-hda-core (D) |  |
| `kmod-sound-hda-core` | D | needs kmod-ledtrig-audio (D) |  |
| `kmod-stmmac-core` | D | needs kmod-phylink (C); needs kmod-pcs-xpcs (D); needs kmod-ptp (C) |  |
| `kmod-switch-ar8xxx` | D | ar8xxx: no 4.19 source |  |
| `kmod-tpm` | D | needs kmod-asn1-decoder (C); needs kmod-asn1-encoder (D); needs kmod-oid-registry (C) |  |
| `kmod-tpm-i2c-atmel` | D | needs kmod-tpm (D) |  |
| `kmod-tpm-i2c-infineon` | D | needs kmod-tpm (D) |  |
| `kmod-trelay` | D | trelay: no 4.19 source |  |
| `kmod-ubootenv-nvram` | D | ubootenv-nvram: no 4.19 source |  |
| `kmod-usb-hid-mcp2221` | D | hid-mcp2221: no 4.19 source |  |
| `kmod-usb-net-aqc111` | D | aqc111: no 4.19 source; needs kmod-usb-net (C) |  |
| `kmod-usb-net-rtl8152` | D | r8152: CONFIG_USB_RTL8152 off; needs kmod-crypto-sha256 (D); needs kmod-usb-net-cdc-ncm (C); needs kmod-usb-net (C) |  |
| `kmod-usb-serial-dmx_usb_module` | D | dmx_usb: no 4.19 source |  |
| `kmod-usb-serial-xr_usb_serial_common` | D | xr_usb_serial_common: no 4.19 source |  |
| `kmod-v4l2loopback` | D | v4l2loopback: no 4.19 source |  |
| `kmod-vfio-pci` | D | vfio-pci-core: no 4.19 source |  |
| `kmod-vhost` | D | vhost: CONFIG_VHOST off; vhost_iotlb: no 4.19 source |  |
| `kmod-vhost-net` | D | vhost_net: CONFIG_VHOST_NET off; needs kmod-vhost (D) |  |
| `kmod-wwan` | D | wwan: no 4.19 source |  |
user packages with a direct dependency on a C or D kmod: 74

luci packages with a direct dependency on a C or D kmod: 2
luci-app-siitwizard, luci-proto-batman-adv
