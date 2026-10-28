# Building the native image

The X28 image has two halves, built in different places because of licensing:

| Half | Contents | Built where |
|---|---|---|
| **Open userspace** | OpenWrt 23.05.5 for `armsr/armv8` (aarch64, runs on the Cortex-A55): base system, netifd, **fw3 + iptables-legacy** instead of firewall4, dnsmasq, dropbear, LuCI | GitHub Actions (`.github/workflows/userspace.yml`) or locally, with [`tools/build/userspace.sh`](../tools/build/userspace.sh) |
| **Vendor half** | stock 4.19 kernel and its 146 modules, the modem/cellular/Wi-Fi binaries, and four 19.07 compatibility libraries | **locally only**, from the unit's own backup (assembly pending; see [#74 input audit](research/native-image-readiness.md)) |

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

## Native-image readiness (2026-10-29, #74)

The [offline audit](research/native-image-readiness.md) verifies the actual local outputs and this unit's
stock inputs. The generic images are not X28 flash images: rootfs images decode to 104 MiB, combined
disk-image gzip members to 243,564,032 bytes, while `rootfs_a` is 64 MiB UBI with a current 31,490,048-byte
`rootfs` volume. The modern tarball has 100 modules for 5.15.167; the stock kernel requires its 146
4.19.205 modules. Vendor bring-up components and compatible module/package/autoload integration are
still needed. The stock boot image can remain unchanged.

The [bounded recovery test](research/changed-page-restore-result.md) has passed; no repeat recovery
drill is proposed. Next is case-sensitive local assembly with selected vendor files, an explicit
network/key-only access and overlay policy, and removal of the effective stock cross-slot clone path.
The stock certificate describes the original SquashFS; changed-content enforcement remains unresolved.
Exact slot selection/reversal and an image-specific deployment operation need review before first-A use.
No existing build output is approved to flash. The local Docker daemon was unavailable during the audit; no assembly or device operation was
performed then. The later private staging result below is still not a bootable image.

## Private staging archive (#76)

`tools/build/stage_native.py` now creates the first **non-flashable** assembled archive. It works
archive-to-archive, preserving case without extracting onto macOS. Run locally with this unit's
verified inputs; do not upload proprietary inputs/outputs into CI:

```sh
python3 tools/build/stage_native.py \
  --stock private/firmware/20261021/rootfs-b-system.tar.gz \
  --modern private/build/out/openwrt-23.05.5-armsr-armv8-generic-rootfs.tar.gz \
  --ipk private/third-party/openwrt-23.05.5/dl/alsa-lib_1.2.9-1_aarch64_cortex-a53.ipk \
        private/third-party/openwrt-23.05.5/dl/libstdcpp6_12.3.0-4_aarch64_generic.ipk \
  --output private/build/native-stage-NEW
```

Output must not exist. `NOT-FLASHABLE`, `manifest.json` and `rootfs-staging.tar.gz` record the result;
`INCOMPLETE` remains if output creation fails. Input hashes describe the exact bytes parsed. The tool
does not authenticate arbitrary input archives: verify originals/build/package checksums beforehand.
It is a local staging tool, with no SSH, USB or flash entry. Outputs contain proprietary code and must
stay under `private/`. The gzip archive is not a UBI image; its byte hash can vary between builds due
to gzip timestamps. The manifest records content provenance, not a claim of bit-reproducible packaging.

The tool preserves modern core files, replaces module/autoload files and kernel/kmod package records
with stock 4.19.205 equivalents, and adds the ten previously link-tested vendor binaries with their
missing ELF library dependencies. Modern libraries are reused by exact requested filename, retaining
the established four older compatibility libraries where names differ. Stock library symlink chains
are preserved. Existing conflicting extra-package files, selected vendor roots, unsafe member paths,
duplicate normalized names, link escapes and merged descendants below non-directories are refused.
Absolute rootfs symlinks remain root-relative links; the tool never follows them into the host.

No stock init scripts or enable links are imported. All `lib/upgrade/*` paths and any
`zmtk_boot_done` path are removed from staging, including generic upgrade helpers; normal sysupgrade
is deliberately unavailable. Kernel package scripts are stored as metadata, never executed. This
removal is not a whole-program proof that no remaining binary can write flash. A future effective
boot tree, overlays and activation paths still require review.

### Observed staging result (2026-10-29)

Private output `private/build/native-stage-76-final/` contains 146 matching stock modules and 24
vendor-closure entries. Its archive SHA-256 is
`58ef3b127f3aa766b63f9d840fcf1d713f2383ab5c294a4ccf88aa719c4ad890`.
Nine synthetic tests pass on Python 3.9 and 3.14, including merged-link/path conflicts and selected-root
symlink terminal collisions. CI runs these using synthetic archives only. The actual output was
extracted in an isolated, network-disabled temporary Linux filesystem: all manifest file hashes and
links matched; `xt_DSCP.ko` and `xt_dscp.ko` survived distinctly; no 5.15 modules or upgrade helpers
remained. Musl `--list` resolved all ten vendor roots and their relocations without executing their
entry points. No router access, firmware service, package hook or device operation was used.

**Remaining integration:** data-only extra-IPK extraction has not installed their control/status
records or executed maintainer scripts; vendor binaries likewise need reviewed package ownership.
Stock module records are transplanted, not evidence that all dependent firmware/config files are
present. Initial modem/mount/network/Wi-Fi activation, device-node/xattr policy, key-only management
access, fresh overlay policy, UBI packaging, signed-content handling and slot selection are unfinished.
The stage has no operational boot guarantee and must not be flashed or booted. Next work integrates
and validates those actual boot-tree requirements before producing a candidate image.
