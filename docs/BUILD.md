# Building the native image

The X28 image has two halves, built in different places because of licensing:

| Half | Contents | Built where |
|---|---|---|
| **Open userspace** | OpenWrt 23.05.5 for `armsr/armv8` (aarch64, runs on the Cortex-A55): base system, netifd, **fw3 + iptables-legacy** instead of firewall4, dnsmasq, dropbear, LuCI | GitHub Actions (`.github/workflows/userspace.yml`) or locally, with [`tools/build/userspace.sh`](../tools/build/userspace.sh) |
| **Vendor half** | stock 4.19 kernel and its 146 modules, the modem/cellular/Wi-Fi binaries, and four 19.07 compatibility libraries | **locally only**, from the unit's own backup (not written yet; see #28) |

**Vendor files never go into the repo, CI, caches, artifacts or secrets.** The repository is public, the files
are proprietary, and they only match this unit's firmware build ([FIRMWARE-INVENTORY.md](FIRMWARE-INVENTORY.md)).

## Open userspace

`userspace.sh` downloads the official 23.05.5 ImageBuilder, checks it against a pinned SHA-256, and assembles
a rootfs from prebuilt packages (no compiling; a few minutes). Package choices, from the firmware inventory:

- `-firewall4 -nftables -kmod-nft-offload`, `+firewall iptables-legacy ip6tables-legacy`: the stock kernel has
  no `nf_tables`, and fw3 fits its iptables modules (gaps: no `ip6table_raw`, `xt_hashlimit` or flow offload).
- LuCI from parts (`luci-base`, `luci-mod-admin-full`, `luci-theme-bootstrap`, `luci-app-opkg`, `uhttpd`,
  `rpcd-mod-luci`), because the `luci` meta-package pulls in `luci-app-firewall`, which expects firewall4.
- The script fails if `firewall4` or `nftables` end up in the manifest.

The result includes armsr's 5.15 kernel modules (pulled in by package dependencies); the local assembly step
will replace them with the stock 4.19 ones.

First local build (2026-10-23, emulated x86_64 on an M-series Mac, 5.5 min): **177 packages**, a 4.7 MB
`openwrt-23.05.5-armsr-armv8-rootfs.tar.gz`. Included: `firewall` (fw3), iptables 1.8.8 in legacy mode
(`iptables-zz-legacy`, `ip6tables-zz-legacy`, `xtables-legacy`), `netifd`, `dnsmasq`, `dropbear`,
`procd`, musl `libc 1.2.4` and LuCI (`luci-base`, `luci-mod-admin-full`, `luci-theme-bootstrap`,
`luci-app-opkg`, `uhttpd`, `rpcd`). No `firewall4` or `nftables`. Also present and to be replaced: the armsr
5.15 kernel and 86 `kmod-*` packages. ImageBuilder also writes armsr disk images (`*-combined.img.gz`,
`*-rootfs.img.gz`) that the X28 does not use.

### In CI

The workflow runs on pull requests that touch `tools/build/` or the workflow, and on manual dispatch
(Actions → userspace → Run workflow). The artifact `x28-userspace-23.05.5` holds the rootfs tarball, the
package manifest and `sha256sums`.

### Locally

On Linux x86_64, on a **case-sensitive** filesystem (ImageBuilder refuses others), with the usual OpenWrt
host tools (`build-essential`, `libncurses-dev`, `zlib1g-dev`, `gawk`, `git`, `gettext`, `libssl-dev`,
`xsltproc`, `rsync`, `wget`, `unzip`, `python3`, `python3-distutils`, `file`, `xz-utils`, `zstd`):

```bash
tools/build/userspace.sh out
```

On an Apple Silicon Mac, in an emulated x86_64 container. `WORK` must stay inside the container, because the
Mac's APFS volume is case-insensitive; only the output goes to `private/build/out`:

```bash
docker run --rm --platform linux/amd64 -e WORK=/tmp/work -v "$PWD/tools/build:/src:ro" -v "$PWD/private/build:/b" ubuntu:22.04 \
  bash -c 'apt-get update && apt-get install -y build-essential libncurses-dev zlib1g-dev gawk git gettext libssl-dev xsltproc rsync wget unzip python3 python3-distutils file xz-utils zstd curl ca-certificates && /src/userspace.sh /b/out'
```

## Not done yet

- Local assembly with the vendor half into a `rootfs_a` image.
- Any flashing: blocked until UART works (#2) and a spare unit is available ([RECOVERY.md](RECOVERY.md), step 7).
