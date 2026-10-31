# Building the native image

The X28 image has two halves, built in different places because of licensing:

| Half | Contents | Built where |
|---|---|---|
| **Open userspace** | OpenWrt 23.05.5 for `armsr/armv8` (aarch64, runs on the Cortex-A55): base system, netifd, **fw3 + iptables-legacy** instead of firewall4, dnsmasq, dropbear, LuCI | GitHub Actions (`.github/workflows/userspace.yml`) or locally, with [`tools/build/userspace.sh`](../tools/build/userspace.sh) |
| **Vendor half** | stock 4.19 kernel and its 146 modules, the modem/cellular/Wi-Fi binaries, and four 19.07 compatibility libraries | **locally only**, from the unit's own backup (assembly pending; see [#74 input audit](research/native-image-readiness.md)) |

> **Current state, 2026-10-29 (`v0.22.0`):** the assembly is no longer pending. The pipeline is `userspace.sh` (CI) →
> `stage_native.py` → `first_boot.py` → `package_ubi.py` (offline container) → a guarded `slot_entry.py` flash to slot A
> ([RECOVERY](RECOVERY.md)). The sections below are in the order the pieces were built and keep their dated notes;
> older statements such as "no WAN interface, DHCP server or web service" describe that day's profile, not today's. The
> image now ships: the `x28-*` packages, LuCI, `dnsmasq`, the firewall, Wi-Fi, LEDs, the modem stack at boot,
> `S95done` (overlay persistence), an empty root password (SSH key-only on port 22) and `x28-bootok`. Sections
> [#122](#live-lan-dhcp-and-front-leds-on-slot-a-122), [#143](#root-password-and-overlay-persistence-143) and
> [#145](#boot-tries-reset-and-ssh-on-port-22-145) are the most recent.

**Vendor files never go into the repo, CI, caches, artifacts or secrets.** The repository is public, the files
are proprietary, and they only match this unit's firmware build ([FIRMWARE-INVENTORY.md](FIRMWARE-INVENTORY.md)).

## Open userspace

`userspace.sh` downloads the official 23.05.5 ImageBuilder, checks it against a pinned SHA-256, and assembles
a rootfs from prebuilt packages (no compiling; a few minutes). Package choices, from the firmware inventory:

- `-firewall4 -nftables -kmod-nft-offload`, `+firewall iptables-legacy ip6tables-legacy`: the stock kernel has
  no `nf_tables`, and fw3 fits its iptables modules (gaps: no `ip6table_raw`, `xt_hashlimit` or flow offload).
- LuCI from parts (`luci-base`, `luci-mod-admin-full`, `luci-theme-bootstrap`, `luci-app-opkg`, `uhttpd`,
  `rpcd-mod-luci`), plus `luci-app-firewall` (it needs only `uci-firewall`, which fw3 provides), `luci-proto-ipv6`
  and `luci-proto-ppp` (#164). The kernel has PPPoE and `ip6tnl` (DS-Lite) but no `sit`, so 6in4/6rd don't work.
- The script fails if `firewall4` or `nftables` end up in the manifest.

The result includes armsr's 5.15 kernel modules (pulled in by package dependencies); the local assembly step
will replace them with the stock 4.19 ones.

First local build (2026-10-23, emulated x86_64 on an M-series Mac, 5.5 min): **177 packages**, a 4.7 MB
`openwrt-23.05.5-armsr-armv8-rootfs.tar.gz`. Included: `firewall` (fw3), iptables 1.8.8 in legacy mode
(`iptables-zz-legacy`, `ip6tables-zz-legacy`, `xtables-legacy`), `netifd`, `dnsmasq`, `dropbear`,
`procd`, musl `libc 1.2.4` and LuCI (`luci-base`, `luci-mod-admin-full`, `luci-theme-bootstrap`,
`luci-app-opkg`, `luci-app-firewall`, `luci-proto-ipv6`, `luci-proto-ppp`, `uhttpd`, `rpcd`). No `firewall4` or `nftables`. Also present and to be replaced: the armsr
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

## First-boot management profile (#78)

`tools/build/first_boot.py` applies a narrow management policy to a verified #76 staging archive.
This is still **NOT-FLASHABLE**; it is not full hardware or boot integration.

```sh
python3 tools/build/first_boot.py \
  --stage private/build/native-stage-76-final \
  --public-key ~/.ssh/router.pub \
  --stock private/firmware/20261021/rootfs-b-system.tar.gz \
  --output private/build/native-management-NEW
```

The public key is parsed as one plain Ed25519 or RSA key (RSA at least 2048 bits); options, private
keys, multiple lines and malformed blobs are refused. Comments are discarded. No private key or
password is read/generated/copied. The archive embeds the public key privately as mode-0600
`/etc/dropbear/authorized_keys`; public keys and per-unit output are not committed. Input archive
bytes must match the stage manifest and its `NOT-FLASHABLE` marker. Existing output is refused.

The profile writes static `192.168.70.1/24` on `eth0.3` (switch profile below; #86 replaced the earlier
`--lan-device` choice). SSH is port 22 (2222 on images before #145), restricted to LAN, with both password-auth options off and all shadow
password fields locked. There is no WAN interface, DHCP server, web service or modem/Wi-Fi service
activation. A laptop would need a compatible static address; no live network was changed here.
`eth1` in the private draft is **not a verified physical-port mapping**. Read-only observation of the
stock unit found `br0` using `eth0.1/.2/.3`, `eth1` and Wi-Fi/USB peers; it does not establish that
plain generic netifd initialization will program the switch or expose a working port.

Enabled startup links are limited to urngd, boot, system, sysctl, log, dropbear and network. Each
retained rc name must be a symlink to the exact corresponding executable regular init script; an
allowed basename pointing elsewhere is refused. Other rc links, board/default scripts, upgrade
helpers, previous SSH keys and `zmtk_boot_done` paths are removed. Normal inittab has no interactive
getty/askfirst entry. Packaged `lib/preinit/*failsafe*` hooks are removed and
`pi_preinit_no_failsafe="y"` is set. This intentionally removes normal OpenWrt failsafe recovery;
it does not establish USB/BROM or arbitrary-damage recovery. `/etc/rc.local` is a no-op and fstab
contains no shared-volume/swap entries. Stock vendor mount/restore init is not imported: that path
would create volumes and write shared NVRAM/config and cannot be enabled as an unreviewed default.

**Observed offline checks:** five synthetic tests pass on Python 3.9 and 3.14, covering malformed
keys/device injection, changed-stage identity, forbidden startup paths, exact rc targets, all-account
locks, failsafe removal, and output preservation. The private draft
`private/build/native-management-78-reviewed/` was extracted in an isolated network-disabled Linux
container. Target UCI parsed the generated network/Dropbear configuration and the effective startup
links/account locks matched the manifest. No SSH/network/vendor daemon was started. The prior #76
userspace CI build also passed after its merge.

**Still pending:** actual key authentication with locked root; kernel/driver/modem/mount/Wi-Fi
activation; physical switch setup; fresh overlay implementation; package registration; device nodes/
xattrs; UBI generation and inspection; signature-content behavior; safe slot selection/reversal.
The existing stock module autoload set and modern preinit/core boot still execute in a future boot;
removing service links is not a whole-system guarantee against hardware activity or flash writes.
Any later merged/overlaid tree must be rechecked for startup overrides. This profile must not be
flashed; a candidate requires the outstanding integration and separately approved device operation.

## Experimental UBI packaging (#80)

`tools/build/package_ubi.py` now packages a verified private management profile in Linux. It creates
SquashFS/XZ, a **fresh empty UBIFS overlay**, and a UBI container with this unit's observed volume
reservations. This is an offline packaging result, **not flash/boot approval**. Stock boot and signature
partitions are neither changed nor generated. No captured writable overlay is reused.

Build the local tooling image (public tools only), then run with networking disabled and private
inputs read-only. The output parent must exist and the output directory must not:

```sh
docker build -t x28-firmware-tools:ubi -f tools/firmware/Dockerfile tools/firmware
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --tmpfs /tmp:rw,exec,size=768m \
  -v "$PWD/tools:/tools:ro" \
  -v "$PWD/private/build/native-management-78-reviewed:/profile:ro" \
  -v "$PWD/private/build:/out" x28-firmware-tools:ubi \
  python3 /tools/build/package_ubi.py --profile /profile --output /out/native-ubi-NEW
```

The tool verifies the exact profile hash and non-flashable marker, validates archive paths/link
ancestry before extraction, and refuses a case-insensitive scratch filesystem. SquashFS uses XZ,
262,144-byte blocks, root ownership, no xattrs, and one compression worker. `mkfs.ubifs` creates
only an empty tree with minimum I/O 4096, LEB 253952 and maximum 116 LEBs. `ubinize` uses PEB 262144,
minimum/subpage I/O 4096 and VID offset 4096 (data offset 8192), with dynamic volumes:

- ID 0 `rootfs`: 124 reserved LEBs / 31,490,048 bytes;
- ID 1 `rootfs_data`: 116 reserved LEBs / 29,458,432 bytes.

Outputs include `rootfs.squashfs`, `rootfs_data.ubifs`, `rootfs-experimental.ubi`, a full 64 MiB
`rootfs-a-experimental.bin` padded with `ff`, command/version provenance, `manifest.json`, and
**`NOT-FLASHABLE`**. `INCOMPLETE` remains if packaging/validation fails. Names describe intended
format/target, not permission to use a flash command. Package/build timestamps and UUIDs mean
byte-identical reproduction is not promised; record the actual manifest for each run.

The independent parser checks every populated EC/VID header CRC, fixed geometry/copy/compat fields,
image sequence agreement, both layout copies and all 128 volume-table records, refusing extra
volumes. Data LEBs must be contiguous/unique and inside the fixed reservation. It checks SquashFS
format/size, UBIFS superblock CRC and min-I/O/LEB/current/max geometry. It also compares the **entire**
reconstructed volume payloads to the actual generated filesystem files plus `ff` tails, including
non-superblock UBIFS data, then repeats inspection after whole-partition padding. Header inspection
alone is not full UBIFS validation or a kernel mount test.

### Observed packaging result (2026-10-29)

Private output `private/build/native-ubi-80-reviewed/` passed generation and independent checking:

| Item | Result |
|---|---|
| SquashFS `bytes_used` | 7,685,384; below the fixed rootfs volume capacity |
| SquashFS digest over `bytes_used` | `1934e74fbbea68df203b189da35d21fdcd6f6d3686a638de33beb0c4b5ae5f2d` |
| Populated data LEBs | rootfs 31; fresh overlay 13; layout copies 2 |
| Full 64 MiB padded-image SHA-256 | `72d8290b3753eff435e635cdfe882751623a551651e0ff28e30281bc6c0c6995` |
| Tools | squashfs-tools 4.6.1; mkfs.ubifs/ubinize mtd-utils 2.3.0 |
| Filesystem reconstruction | 1,209 regular files plus links match the private profile; 146 stock modules retained |
| Fresh overlay | UBI Reader extracted it with no user files; no captured settings imported |

Five synthetic tests pass on Python 3.9 and 3.14, including recomputed-CRC semantic corruption,
extra volume records, other-overlay-block corruption, invalid geometry/duplicate blocks, and
input-identity/existing-output rejection. CI needs no vendor inputs or external filesystem tools for
these tests. The actual build and independent unsquashfs/UBI Reader extraction ran in isolated,
network-disabled containers without executing image code or accessing the router.

The digest differs from the stock signed digest; this package does not resolve content enforcement
or create a vendor signature. Key login, physical Ethernet/switch initialization, vendor activation,
package ownership, device nodes/xattrs, actual fresh-overlay mount behavior, and slot selection/
reversal remain unproven. The next step is isolated runtime management validation and first-A boot
planning. There is no proposal to repeat the completed recovery drill or flash this artifact yet.

## Isolated packaged SSH authentication (#82)

The packaged Dropbear/dbclient pair now passes a runtime authentication test with root's password
field locked as `!`: a generated authorized Ed25519 key succeeds, a different key fails, and the
same key fails after the authorization file is emptied. No password is supplied. This settles the
narrow locked-account/key-authentication concern from #78 for these binaries on the container's
kernel. It is **not** a native X28 boot, actual management-key test or procd/network-service test.

```sh
docker run --rm --network none --read-only --cap-drop ALL \
  --cap-add SYS_CHROOT --cap-add SETUID --cap-add SETGID \
  --security-opt no-new-privileges --tmpfs /tmp:rw,exec,size=512m \
  -v "$PWD/tools/build:/tools:ro" \
  -v "$PWD/private/build/native-ubi-80-reviewed:/candidate:ro" \
  x28-firmware-tools:ubi python3 /tools/management_auth_test.py /candidate
```

The check requires Docker root and refuses an active non-loopback interface. Docker may expose
inactive default tunnel devices; those are allowed, but no interface except `lo` may be up. No
network-administration capability or host network is provided. The script verifies the candidate
SquashFS digest/non-flashable marker, extracts only into temporary scratch, parses the actual UCI
password/root-login/port/LAN settings and checks locked root. The test server uses the equivalent
`-s -g` authentication flags but overrides binding to `127.0.0.1:2222`; it does **not** start the init
script, netifd or any vendor daemon. `dbclient -y` trusts only the temporary test server's ephemeral
host key in this isolated namespace; that is not the policy for accessing the real router.

Client, wrong-client and host keys are generated in the scratch tree and deleted with it. The real
profile's public key is replaced **only in that temporary tree**; the private candidate is read-only,
and no user private key/password is accessed or stored. Client stdin is empty and each command has
a timeout. Every result is asserted, and the server is terminated in a finally block. The only remote
command is an `echo` marker inside the same scratch root. No firmware/vendor entry point executes.

Observed result against SquashFS digest
`1934e74fbbea68df203b189da35d21fdcd6f6d3686a638de33beb0c4b5ae5f2d`: **PASS** for authorized key,
wrong-key rejection, empty-authorization rejection and locked root. The tool emits a sanitized JSON
summary without keys; generated private keys never leave the temporary container filesystem.

Still unverified: this unit's actual public-key/client combination, full Dropbear UCI service startup,
procd/overlay boot, physical Ethernet/switch setup, vendor activation, signed-content acceptance and
slot selection/reversal. The candidate remains **NOT-FLASHABLE**. Next work targets effective first-A
boot/management behavior and exact slot policy, without another recovery-write rehearsal.

## Live management and slot prerequisites (#84)

The [read-only device check](research/live-native-boot-prerequisites.md) found the connected stock
switch path on VLAN 3 (`4 5t`), with `eth0.3` carrying traffic and draft-selected `eth1` lacking
carrier. The candidate currently lacks `swconfig` and the generic switch helper. It needs explicit
reviewed switch integration before the static LAN configuration can be considered reachable.
Stock B and all four selection records remain unchanged; a safe A-selection/reversal API is not yet
established. No setting or partition was changed. See the report for exact live/source evidence.

## Observed socket-4 switch profile (#86)

`first_boot.py` now also needs `--stock` (the case-preserving stock rootfs archive). It copies this
unit's stock `/sbin/swconfig` (SHA-256 `1fe11f5c9b3a5b04241d49ab689227869ca7d77d4a838fb01e9931954778179c`);
every `DT_NEEDED` entry already resolved in the staged tree (`libnl-tiny`, `libuci`, `libubox`,
`libgcc_s`, musl) and an unresolved library refuses the build. LAN is `eth0.3`. `/etc/config/network`
carries `switch0` with the table observed on stock in #84 (VLAN 1 `1 5t`, 2 `2 5t`, 3 `4 5t`, 4 `0 6t`,
each untagged port's PVID equal to its VLAN), and `/etc/init.d/x28-switch` (`S18`, before network)
runs `swconfig dev switch0 load network`, then reads back the enable flag, every VLAN's ports and
every PVID. A different `swconfig list` result, a failed load or any mismatch writes
`/tmp/x28-switch.failed` and exits non-zero. No vendor initializer, PHY (`mii_mgr`) or GPIO 24
write, no `lan_mgr`, modem or Wi-Fi start, and the generic `lib/network/switch.sh` is not shipped.

**Observed offline checks (2026-10-29):** nine synthetic tests pass (Python 3.9), including the init
script run against a fake `swconfig` that rejects a wrong switch, a load failure and a drifted table.
The private output `private/build/native-management-86/` (archive
`b7feca9c4a3bf18443d06224a7cba5bd72e6ce3c5cab6b756df8184ee2bfd40b`) was packaged into
`private/build/native-ubi-86/` (SquashFS digest `e841e2d5f280429e27ea095bae99fc04124a232ed34fbfb2d739f1800b142a12`,
31 + 13 LEBs, padded image `9d433b66…`); the independent UBI check passed. In a network-disabled container
the image's musl loader resolved all `swconfig` libraries and the image's own `uci` parsed the network
config. The candidate stays **NOT-FLASHABLE**.

**Not verified:** the real `swconfig` against the real driver (output format of the `get` readbacks is
assumed from its source, not observed here), whether `load` sets PVIDs from `switch_port`, whether netifd's
built-in switch handler re-applies the same table after `S18` (idempotent in design, unobserved), cold-reset
persistence, and that socket 4 is the operator-labelled jack (operator-confirmed once, not independently
measured). Nothing was run on the router.

## Live LAN, DHCP and front LEDs on slot A (#122)

Applied by hand on the running slot-A unit (2026-10-29), then built into `first_boot.py`: the `br-lan` bridge,
an `S19dnsmasq` link (the staged default `dhcp` config already serves `lan`), `sbin/ujail` and its opkg files
removed, and `x28-leds` copied from `package/x28-leds/files` with an `S99` link. A real build against
`native-stage-76-final` passed `ab_guard`; without the modem stack the LEDs show power plus blue (no service).

- **LAN:** `br-lan` bridges `eth0.1 eth0.2 eth0.3 eth1` (sockets 1, 2, 4, 0), like stock `br0`; the switch table
  above is unchanged, so `x28-switch` still validates it. `lan` is static `192.168.70.1/24` on `br-lan`.
- **LAN IPv6 (#126):** `lan` has `ip6assign 64` and odhcpd (S35) sends RA and DHCPv6 on `br-lan` from the /64 the
  cellular WAN hands to netifd (`x28_mipc`, #125); the WAN keeps only a /128 so its on-link /64 does not shadow the LAN.
  Verified on the unit: a LAN client got SLAAC addresses and reached the IPv6 internet.
- **DHCP/DNS:** the vendor kernel has `CONFIG_NAMESPACES` off, so procd's `ujail` fails and every jailed service
  (dnsmasq, sysntpd) exits at start. With `procd-ujail` removed procd runs them unjailed and dnsmasq serves DHCP
  and DNS on the LAN. Images for this kernel must not ship `procd-ujail`.
- **LEDs:** the front LEDs sit behind the Tozed `tz_gpio_leds` driver, not `/sys/class/leds`. `package/x28-leds`
  writes `{u32 status, u32 type, u32 interval_ms}` records to `/dev/tz_gpio_leds` (format from the stock
  kernel's `tz_gpio_leds_write`; types from the device tree and stock `gpiod`): power `0x62`, Wi-Fi `0x06`,
  4G `0x0b`, 5G `0x0c`, signal red `0x20`, green `0x30`, blue `0x40`. `x28-leds selftest` checks the encoding
  and the state mapping. Signal colour (#162), from 5G SS-RSRP or else LTE RSRP: blue >= -70 dBm, green >= -90,
  yellow >= -105, red below; blinking blue while searching.
- **Wi-Fi (#127):** MT7915 DBDC on `mt_wifi` (no nl80211): `ra0` 2.4 GHz, `rai0` 5 GHz, which the driver registers as a
  virtual interface of `ra0` (opens only while `ra0` is up). `package/x28-wifi` is a netifd wireless handler (`mtwifi`):
  it renders `/etc/wireless/mediatek/mt7915.dbdc.b0/b1.dat` from `/etc/config/wireless` on a saved stock copy and
  hands the interface to netifd, which bridges it into `lan`. The image copies `l1profile.dat` and both profiles from
  the stock rootfs; calibration stays in `/mnt/vendor/nvcfg/e2p`. First boot's `wifi config` creates one open AP per
  band (like root's empty password; set both in LuCI on first login).
  Stock LuCI 23.05 builds Wireless Security choices only for `mac80211`/`broadcom` radios, so the builder inserts an
  `mtwifi` branch (WPA2-PSK, WPA3-SAE, mixed modes) into `wireless.js`; it refuses a LuCI build without the anchor.
  LuCI also hides radio and network options for non-mac80211 radios, so the builder adds `mtwifi` blocks for the ones the
  handler maps (#166): `txpower_pct` (`TxPower`, a percentage: the driver has no dBm setting), `beacon_int`, `hidden`,
  `isolate`, `wmm`, `dtim_period`, `macfilter`/`maclist` (`AccessPolicy0`/`AccessControlList0`; the driver renumbers the
  5 GHz BSS to slot 1 in `DBDC_card0.dat`) and `ieee80211w` (`PMFMFPC`/`PMFMFPR`). netifd reads a handler's option list
  only at start, so a new option needs a netifd restart on a running unit. A band whose networks are all disabled can't be
  switched off on its own (`RadioOn=0` turned the whole card's flag off and `ra0` beaconed an open `HT_AP0`): `rai0` goes
  down; `ra0` goes down too unless it has to carry `rai0`, and then it gets a hidden WPA2 network with a random key.
  The frequency widget offers "auto", AC and AX only when hostapd reports `acs`/`11ac`/`11ax`; the builder lets an
  `mtwifi` radio count as having them, and drops the Client and Ad-Hoc modes for it until client mode exists (#175).
  All LuCI edits are anchored string replacements in `first_boot.py` (`luci_edits()`), applied once each.
  LuCI bakes `?v=<revision>` into its header templates and uhttpd serves files dated 1970, so `first_boot.py` appends a hash
  of `www/` to those strings: a browser fetches LuCI's JS and CSS again after an image that changed them (#187).
  Two networks per band (#167): the driver creates `ra1`/`rai1` once, at its first open after loading, from `BssidNum` in the
  profile, so the image ships `BssidNum=2` and the handler always renders it. A second `wifi-iface` on a radio brings the
  extra interface up; without one it stays down and silent (scanned). The MAC address of `rai0` depends on `BssidNum`.
- **Wi-Fi info for LuCI (#165):** `mt_wifi` has no nl80211, so the feed's `libiwinfo` sees no radios. `tools/build/sdk_packages.sh`
  builds iwinfo 2023-07-01 with the SDK and `package/iwinfo-mtwifi/100-mtwifi-backend.patch` (release 2, preferred by
  ImageBuilder): wireless extensions for ESSID/BSSID/channel/mode/bit rate, per-band mode lists, channels from the country's region (no DFS flags), and associated stations from the driver's station table
  (`SIOCIWFIRSTPRIV + 0x1F`, 56-byte entries, the layout stock's `ioctl_helper.so` reads). Tx power, radio signal/noise and
  station data rates stay unknown. On a unit: `iwinfo rai0 info` shows `Type: mtwifi`; `iwinfo rai0 assoclist` lists clients.
- **Wi-Fi country (#177):** `/usr/share/x28-wifi/regions` maps a country to the driver's `CountryRegion` and `CountryRegionABand`, picked
  from the SDK driver's `rt_channel.c` as the largest region that stays inside the country's channels; `channels5` lists each 5 GHz
  region's channels. The merged profile takes the country from the 5 GHz profile, so LuCI sets it on both radios. The driver doesn't
  enforce the region (observed: Iran stayed on 36), so the handler replaces `auto` or a channel the country doesn't allow with the
  region's first channel. `auto` is therefore not an automatic choice.
- **Wi-Fi scan (#176):** the backend's `scanlist` starts a passive `SiteSurvey` at most every 30 s per band, waits 4 s (measured) and reads
  the table with `RTPRIV_IOCTL_GSITESURVEY`. LuCI asks every few seconds, so the other calls read the table only. The driver reports signal in
  percent, so it converts back to dBm (-50 dBm or better shows as -50), and widths above 40 MHz aren't in this table. `sh tests/test_mtwifi_scan.sh`
  checks the line parser.
- **Install space (#183):** Disk space would be only `rootfs_data` (22.8 MB). `lib/preinit/79_x28_user_data` attaches `user_data`
  (ubi1, stock's volumes `customer` and `data`) before `mount_root`, and `etc/config/fstab` makes `data` (278 MB free) the overlay
  through stock OpenWrt's `block extroot`. Nothing is formatted, so stock slot B keeps its files. If the volume is missing or
  doesn't mount, `rootfs_data` serves as before; so it does from slot A's third boot try on, so a bad overlay can't run the
  tries up to stock B's repair (a persistent fault cycles bad, bad, good). `block` binds the overlay to the image's root UUID, so
  the hook starts the overlay fresh on a new image, as flashing does to `rootfs_data`. The image ships only `ubiattach` and
  `ubinfo` of `ubi-utils`; `ab_guard` allows `ubiattach` in that one file only. Limits, see `docs/RECOVERY.md`: the reset button
  and `firstboot` don't clear this overlay, reflashing identical bytes keeps it, and a fall-back boot has `rootfs_data`'s own
  settings (LuCI password empty, new Wi-Fi key and host key). Keep free space on it: stock B's `/data` is the same volume.
- **Modem at boot (#131):** `package/x28-modem` (`S19x28-modem`, before network) creates the `/dev/mtd/<name>` and
  `/dev/block/<name>` links from `/proc/mtd` plus active-slot aliases, mounts the vendor yaffs2 partitions, starts the
  vendor daemons through their own stock init scripts (`nvram_daemon` once, `ccci_fsd`, `ccci_mdinit`, `ql_ril_service`,
  `ql_netd`, `mipc_submonitor`, `atci_service`, `atcid`), creates the one-ACM USB gadget, sends `AT+CFUN=1` and `ifup wan`,
  in the background. The builder copies those init scripts, their binaries (with ELF dependencies) and `vendor/etc`
  from the stock rootfs. Verified live without a reboot: with everything above ccci stopped and the gadget removed, the
  script brought `wan` back in 25 s. A real reboot test waits for slot A to be marked successful (A retry 4, success 0).
- **Overlay:** `/usr` on this unit is unwritable until reboot (an earlier upper-dir removal), so `x28-leds`
  installs to `/sbin`.

## Boot-path guard against flash and other-slot writes (#87)

`tools/build/ab_guard.py` runs inside `first_boot.py` and `package_ubi.py` (and standalone on any
`rootfs-management.tar.gz`). It starts from everything that runs at boot (`inittab`, `rcS`, enabled
`rc.d` links, `rc.local`, preinit, hotplug, cron, uci-defaults), follows every `/etc|/lib|/usr|/sbin|/bin`
path those scripts mention (a deliberate over-approximation: a mentioned directory pulls in all its
scripts), and refuses the build on `ab_image_sync`, `zmtk_boot_done`, `bootctrl`, `platform_do_upgrade`,
`mtd ... write`, `nandwrite`, `flash_erase`, `ubiupdatevol`, `ubiformat`, `sysupgrade` as a command or
`of=/dev/{mtd,ubi,block}`. Any `lib/upgrade/*` or `zmtk_boot_done` path is refused even if unreferenced.
Plain reads (`/dev/mtdblock`, `/sysupgrade.tgz` tests) are allowed.

**Observed (2026-10-29):** six synthetic tests pass (every writer form in an enabled script, in a sourced
library, and in each root type; unreferenced scripts and plain reads pass). The private #86 profile
passes (705 boot-reachable files scanned, no hits), so the stock clone in `zmtk_boot_done`
(`ab_image_sync "_b"` at line 42, retry repair at lines 124-141) has no path into the image.

**Not covered:** this is text only. It does not prove that a vendor ELF, busybox applet or `mount_root`
never writes flash, nor guard against a user later adding such a script to the persistent overlay.
Stock's success handling is gone with the script: slot A's retry/success records are never cleared by
the image, so what LK does on later boots (and any fallback to B) is part of #92 and is unverified.

## Physical console shell (#104)

`first_boot.py` adds `ttyS0::askfirst:/bin/ash --login` to `/etc/inittab` (kernel console `ttyS0,921600n1`) and
refuses a stage without `/bin/ash`. This replaces the earlier no-console profile: failsafe is still removed, SSH is
still key-only and root's password is still locked, but the UART now gives a root shell after Enter, with no
password. It is reachable only through the board's UART pads (1.8 V, shifted; see [RECOVERY](RECOVERY.md)). The
boot-path guard still passes (705 files), and the manifest limits list the console. The first A boot is therefore no
longer kernel-log only; the write plan should say so once #103 lands.

**Observed offline (2026-10-29):** 10 synthetic tests pass; `private/build/native-ubi-104/` (SquashFS digest
`b0696c5b...`, padded image `23127d94...`) passed the independent UBI check; the packaged `inittab` shows the single
console entry, `bin/ash -> busybox` and `dev/console`. **Not verified:** that the prompt appears on hardware, and
that procd creates `/dev/ttyS0` without devtmpfs (stock does the same for its getty).

## Root password and overlay persistence (#143)

Like stock OpenWrt, root starts with an **empty password**: LuCI accepts it and asks you to set one (Network is LAN only; the
`wan` firewall zone rejects input). SSH is unchanged: Dropbear stays key-only (`PasswordAuth` and `RootPasswordAuth` off), so an
empty or any password never works over SSH. The image also enables `S95done` (`mount_root done`); without it `mount_root`
reports 'overlay filesystem has not been fully initialized yet' and discards the overlay at every boot, losing passwords, host
keys and settings. Set the password in LuCI (System > Administration) or with `passwd` over SSH.
The image also writes stock OpenWrt's NTP section (`*.openwrt.pool.ntp.org`) and enables `S98sysntpd` (#169): the unit
boots with its clock at 2010-01-01, and HTTPS (`opkg`, LuCI Software) fails until the clock is set.

## Boot tries reset and SSH on port 22 (#145)

The preloader adds one "tries" to the A record in all four `misc` copies on every boot (observed 0 -> 1 after a reboot). Stock
resets it to 0 after each good boot; the native image did not, so a healthy slot A would run out of its inferred 7 tries and
stock B would repair (erase) it. `x28-bootok` (START=96) does what stock does: once Dropbear and the LAN are up, on slot A only,
it writes 0 to the A tries byte of each copy that is not 0 (copy at 0x800 last, after checking all four are boot-control
records and reading each byte back), with the stock `dd-nand` + `libnandapi.so` copied into the image. It never writes the
success byte, priorities or any other partition; a boot that never reaches it keeps counting, so the fall-back to B stays.
`ab_guard` allows the `dd-nand` token in that one script only while it keeps the reviewed shape. Dropbear now listens on
port 22 (LAN only, key-only), like standard OpenWrt; update `~/.ssh/config` and the known_hosts entry when you flash it.
If one write fails, earlier copies stay at 0 and later ones keep their tries (a mixed record, which the preloader's handling of is unverified); the next boot retries.
