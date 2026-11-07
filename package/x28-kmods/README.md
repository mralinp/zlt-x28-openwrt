# x28-kmods

Kernel modules the vendor 4.19.205 kernel lacks, built for it from source, and `x28-kmods`, the init script that loads
them safely at boot (`files/x28-kmods.init`).

| Module | Source | Why |
|---|---|---|
| `wireguard` | `src/wireguard`: [wireguard-linux-compat](https://github.com/WireGuard/wireguard-linux-compat) v1.0.20220627 (tag tarball sha256 `7bd8ea94...36d0`), `src/` only, plus `src/x28-wireguard.patch` | WireGuard (#227) |
| `nf_socket_ipv4/6`, `nf_tproxy_ipv4/6`, `xt_socket`, `xt_TPROXY` | `src/tproxy`: unchanged files from Linux v4.19.205 (`net/ipv4/netfilter`, `net/ipv6/netfilter`, `net/netfilter`) | TPROXY for Passwall2 (#198) |
| `x28_udp_lookup` | `src/tproxy/x28_udp_lookup.c` (ours) | exports `udp4_lib_lookup`/`udp6_lib_lookup`, which the stock kernel never exported |

`src/feed` holds modules that are not part of the image but ship as real packages in the X28 feed (#395): unchanged Linux
v4.19.205 files, built into `/out/feed/`. `package/x28-kmod-stubs/real.txt` lists the package each one belongs to, and
`kmod_stub_feed.py build --kmods DIR/feed` packs them into `/lib/modules/x28`, where `x28-kmods` loads them after boot.

| Module | Source | Package | Why |
|---|---|---|---|
| `act_gact` | `src/feed/act_gact.c` (`net/sched/act_gact.c`) | `kmod-sched-core` | the only module of that package the vendor kernel lacks; `tc-full` needs the package |
| `veth` | `src/feed/veth.c` (`drivers/net/veth.c`) | `kmod-veth` | virtual Ethernet pairs (containers, tests) |
| `macvlan` | `src/feed/macvlan.c` (`drivers/net/macvlan.c`) | `kmod-macvlan` | `keepalived` |
| `sch_cake` | `src/feed/sch_cake.c` (`net/sched/sch_cake.c`) | `kmod-sched-cake` | SQM (`sqm-scripts`) |
| `algif_aead`, `algif_rng` | `src/feed/` (`crypto/`) | `kmod-crypto-user` | OpenSSL AF_ALG engine, `cryptsetup`; the vendor kernel has the other four modules |
| `xt_hashlimit` | `src/feed/xt_hashlimit.c` (`net/netfilter/`) | `kmod-ipt-hashlimit` | `shorewall` |
| `raw_diag` | `src/feed/raw_diag.c` (`net/ipv4/`) | `kmod-inet-diag` | `sing-box` |
| `netlink_diag` | `src/feed/netlink_diag.c` (`net/netlink/diag.c`, renamed; needs `af_netlink.h`) | `kmod-netlink-diag` | `ss` |
| `usbip-core` | `src/feed/usbip_*.c` (`drivers/usb/usbip/`) | `kmod-usbip` | `usbip` |
| `act_csum`, `act_pedit`, `act_simple`, `em_cmp`, `em_meta`, `em_nbyte`, `em_text`, `sch_codel`, `sch_fq`, `sch_gred`, `sch_multiq`, `sch_sfq`, `sch_teql` | `src/feed/` (`net/sched/`) | `kmod-sched` | `luci-app-splash`, `tunneldigger-broker` |
| `act_bpf` | `src/feed/act_bpf.c` | `kmod-sched-bpf` | `bridger`, `uspot` (`cls_bpf` is built in) |
| `ipt_ah`, `xt_esp`, `xt_policy` | `src/feed/` (`net/ipv4/netfilter/`, `net/netfilter/`) | `kmod-ipt-ipsec` | `strongswan`, `libreswan` helpers |
| `nbd` | `src/feed/nbd.c` (`drivers/block/`) | `kmod-nbd` | `nbd`, `qemu-nbd` |
| `spidev` | `src/feed/spidev.c` (`drivers/spi/`) | `kmod-spi-dev` | `spidev-test` |
| `cdc-acm` | `src/feed/cdc-acm.[ch]` (`drivers/usb/class/`) | `kmod-usb-acm` | USB serial modems |
| `bonding` | `src/feed/bond_*.c` (`drivers/net/bonding/`) | `kmod-bonding` | `proto-bonding` |

| `ip6table_raw` | `src/feed/ip6table_raw.c` (`net/ipv6/netfilter/`) | `kmod-ipt-raw6` | `shorewall6` |
| `nfnetlink_log` | `src/feed/nfnetlink_log.c` (`net/netfilter/`; needs `src/bridge/br_private.h`) | `kmod-nfnetlink-log` | `libnetfilter-log1` |
| `act_vlan`, `cls_flower` | `src/feed/` (`net/sched/`) | `kmod-sched-act-vlan`, `kmod-sched-flower` | `bridger` |
| `uleds` | `src/feed/uleds.c` (`drivers/leds/`) | `kmod-leds-uleds` | `bluld` |
| `ledtrig-usbport` | `src/feed/ledtrig-usbport.c` (`drivers/usb/core/`) | `kmod-usb-ledtrig-usbport` | `luci-app-ledtrig-usbport` |
| `dummy` | `src/feed/dummy.c` (`drivers/net/`) | `kmod-dummy` | netifd `dummy` interfaces |

| `libchacha`, `libpoly1305`, `chacha_generic`, `poly1305_generic`, `chacha20poly1305` | **private SDK tree** (`crypto/`, `lib/crypto/`); only `src/sdk/Kbuild` is here | `kmod-crypto-chacha20poly1305` | `strongswan-mod-chapoly` |

The vendor kernel has the 5.x crypto library rework backported (`crypto/chacha.h`, `lib/crypto/`), so vanilla 4.19.205 files do not build
for it. `build.sh` copies those files from the SDK tree into its container only; they never enter the repository, and only the built
`.ko` files are published (as for the native image, #254). Load order matters: the two libraries first.

`kmod-sched-connmark` has no module to build (`act_connmark` is on the unit) and is only a package that depends on `kmod-sched-core`.
Not done: `kmod-ipt-ipset` (the vendor-ipset path in `docs/research/vendor-ipset-packaging.md` covers it), `kmod-iscsi-initiator`, `kmod-ipt-quota2` (its source, `xt_quota2`, exists only in the vendor SDK tree, not in Linux 4.19.205, and is not used) and `kmod-hwmon-*`/`kmod-thermal` (no user package depends on them).

`algif_*` link against the vendor `af_alg.ko`, `xt_hashlimit` against `x_tables.ko`, `ip6table_raw` against `ip6_tables.ko` and `nfnetlink_log` against `nfnetlink.ko`, so `x28-kmods` loads those first.

The patch drops wireguard-linux-compat's `ktime_get_coarse_boottime_ns()`, which the vendor tree already defines.

Build (needs the private SDK tree in the `x28-kbuild` volume, see [BUILD](../../docs/BUILD.md)):

```sh
docker run --rm -v x28-kbuild:/k -v "$PWD/package/x28-kmods:/src:ro" -v "$PWD/private/kmods:/out" \
  debian:bookworm bash /src/build.sh
```

The SDK tree and the built `.ko` files stay private: only these sources are published. A rebuild on 2026-11-02 matched
the modules on the test unit section for section (`.text`, `.rodata`, `.data`, init and exit code); the files differ
only in embedded build paths.

Licence: GPL-2.0, as each file states (`src/wireguard/COPYING`), unlike the rest of this repository.
