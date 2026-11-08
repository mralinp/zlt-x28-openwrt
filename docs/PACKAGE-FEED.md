# The X28 package feed

**Supported for one device line only: the ZLT X28 and its rebrands (MediaTek MT6890, vendor kernel 4.19.205, aarch64,
OpenWrt 23.05.5 userspace).** The feed carries kernel packages built for that exact kernel and its config. It is not valid for
other devices or kernels, and nothing here makes the official 23.05 kernel packages (5.15) work.

The feed is a normal signed `opkg` feed, published as the newest GitHub release of this repository:

```text
src/gz x28 https://github.com/mralinp/zlt-x28-openwrt/releases/latest/download
```

Images built with the flasher since mralinp/x28-flasher#72 carry this line and the key; older images carry the `feed-2`
line (see "Using it" to switch). Signing key fingerprint:
**`7fec994ab0d15b97`** (`package/x28-feed/files/x28-feed.pub`, installed as `/etc/opkg/keys/7fec994ab0d15b97`). `opkg`
checks the signature; do not turn that off.

## What it does

The official feeds carry about 10 000 userspace packages that run on this device as they are, and 976 kernel-module packages
(`kmod-*`) built for kernel 5.15. The X28 runs a vendor 4.19.205 kernel, so the official `kmod-*` packages can never load.
This feed makes `opkg` tell the truth about that kernel:

| What | Count | Meaning |
|---|---|---|
| `kernel` record | 1 | marks the running kernel as installed, so packages that need `kernel (= …)` resolve |
| Stubs | 180 | empty `kmod-*` packages for modules the kernel already has (built in or shipped by the vendor), so userspace that depends on them installs |
| Built modules | 28 | `kmod-*` packages that carry modules the vendor kernel lacks, built for it (version `1:4.19.205-x28-r1`) |
| Vendor ipset | 3 | `ipset`, `libipset13` and a marker, for the vendor kernel's ipset set types |

A package that needs a kernel module the feed has neither stubbed nor built **fails to install with a clear error** instead
of installing something that cannot load. That is by design: `opkg install kmod-nft-core` is refused, not broken.

All versions carry the epoch `1:`, so they outrank the official 5.15 packages. `opkg` may print
`cannot find dependency kernel (= 5.15…)` while installing; it refers to the official record it is ignoring, and the install
continues.

## What is covered

Of the 976 official 23.05 kmods (see [the gap analysis](research/kmod-gap.md)):

- **208** install: 180 stubs and 28 built modules. This includes WireGuard (`kmod-wireguard`) and the TPROXY/socket modules for
  Passwall2 (`kmod-ipt-tproxy`, `kmod-ipt-socket`), which the image also preinstalls, SQM (`sqm-scripts`, `sch_cake`), `tc-full`, `veth`, `macvlan`,
  `bonding`, `nbd`, `usbip`, `ss` (netlink/raw diag), `iptables-mod-hashlimit`, `iptables-mod-ipsec`,
  the IPv6 raw table (`kmod-ipt-raw6`), ChaCha20-Poly1305 for strongSwan, flower/vlan/bpf traffic control, `dummy`, `uleds`, and the USB serial driver `cdc-acm`.
  **24 of the 27** kmods that some user package depends on are covered. The other three: `kmod-ipt-ipset` (covered by the vendor
  ipset packages instead), `kmod-ipt-quota2` (its source exists only in the vendor SDK) and `kmod-iscsi-initiator`
  (skipped; needs a SCSI transport module for one niche package).
- **About 190** more are buildable out of tree but not built, because no package depends on them (network and SATA drivers
  for hardware this SoC does not have). They can be added on request.
- **578** need a kernel change or a backport, and stay refused: `nftables`/`firewall4`, `ksmbd`, DES-based IPsec,
  Bluetooth, the Wi-Fi stack (`cfg80211`), namespaces, and similar. the gap analysis, made before WireGuard and TPROXY became packages, counted 74 user packages that depend directly on one of them; the
  firewall stays `fw3` with iptables. Getting these means a new kernel, which is [#130](https://github.com/mralinp/zlt-x28-openwrt/issues/130)
  and a flash with brick risk.

LuCI itself is not affected: only two `luci-*` packages (`luci-app-siitwizard`, `luci-proto-batman-adv`) depend directly on a
refused module.

## Package model and updates

Everything we build is a package in this feed, and the image installs the same files (one build, used twice: see "How a release is made").
Three groups:

| Group | Packages | On the image | If the user removes it |
|---|---|---|---|
| **Required** | `x28-base` and what it depends on: `x28-kmods` (module loader), `x28-storage` (overlay), `x28-bootok` (A/B boot counter), `x28-dhcp`, `x28-leds`, `x28-modem`, `x28-mipc` with `luci-proto-x28-mipc` (5G WAN), `x28-nrband` (5G band tool), `x28-switch` (LAN switch), `x28-wifi` | yes | `opkg` refuses while `x28-base` is installed (`--force-depends` overrides it, on the user); reinstall from the feed |
| **Preinstalled, optional** | `kmod-wireguard`, `kmod-ipt-tproxy`, `kmod-ipt-socket` (what Passwall2 and WireGuard need), `ipset` with its libraries | yes | `opkg install` brings it back |
| **On demand** | the other built module packages and the stubs | no | `opkg install` when something needs them |

Not in the feed, and never will be: the vendor parts (the kernel, the modem stack, the `mt_wifi` driver and firmware); they come from the unit's own
backup. Also image-only for now: `iwinfo-mtwifi` (ImageBuilder builds it) and the feed key (the trust anchor must not update itself). `x28-nrband` is built against the unit's own `libmipc_msg.so` (`tools/build/x28_nrband.sh`), so like the module packages it is built locally, published on the feed release and pinned by hash.
**Passwall2** (`luci-app-passwall2`, `xray`) stays on its own third-party feed, which the image lists next to ours.

**Updating.** `opkg update && opkg upgrade` updates all of it, ours included; a package only changes when its version number does. The
boot-critical ones (`x28-bootok`, `x28-kmods`, `x28-modem`) are replaced on disk at once, but the running daemon or the loaded modules change at the **next
reboot**, so reboot after upgrading them. A module package never replaces a loaded module until then.

**Rolling back.** The feed keeps one current version per package, but the older `.ipk` files stay on the feed release until we clean them up, and every
firmware release bundle holds the exact set it was made from. This `opkg` cannot install from a URL, so download the file first, then install it from `/tmp`:

```sh
cd /tmp && uclient-fetch -O x28-base_0.1.0-1_all.ipk https://github.com/mralinp/zlt-x28-openwrt/releases/latest/download/x28-base_0.1.0-1_all.ipk
sha256sum x28-base_0.1.0-1_all.ipk     # compare with the bundle's SHA256SUMS
opkg install --force-downgrade /tmp/x28-base_0.1.0-1_all.ipk
```

The `-rN` revisions order correctly. Reboot afterwards if the package is a boot-critical one. `opkg upgrade x28-base` goes forward again. Tested on a unit with `x28-base`
([TESTING 50](TESTING.md#50-rolling-back-and-forward-an-x28-package-on-a-unit-2026-11-08)); the boot-critical packages were not rolled back.

## Using it

On an image built with the current flasher the line and the key are already there. On a running unit or an older image:

```sh
# the key ships with images; check it
ls /etc/opkg/keys/7fec994ab0d15b97
# replace an older x28 line (feed-1, feed-2) with the stable URL
sed -i 's|^src/gz x28 .*|src/gz x28 https://github.com/mralinp/zlt-x28-openwrt/releases/latest/download|' /etc/opkg/customfeeds.conf
opkg update
opkg upgrade kmod-sched-core   # or any built module; see `opkg list-upgradable`
```

Built modules are installed in `/lib/modules/x28/`, out of reach of the kernel's on-demand `modprobe`. Each module package also
ships a list, `/etc/x28-kmods.d/NN-<package>` (`NN` is 50 plus its depth among our packages, so a package loads after the ones it
needs). The loader, the `x28-kmods` package, reads its short built-in list and then those files and loads the modules about 30
seconds after boot, once `x28-bootok` has reset the A/B boot counter; it stops after three loads in a row that did not finish, so
a bad module cannot cause a boot loop. `/etc/init.d/x28-kmods modules` prints what it would load, in order. Installing or removing
a module package adds or removes its modules from the load; nothing else is edited. **A unit or image that still has the old loader
(a fixed list baked into the image) needs `opkg install x28-kmods` once**; it replaces the old script and from then on every
module package loads itself. Until then, load newer modules by hand with `insmod /lib/modules/x28/<name>.ko`.

A newly built version of a module has a higher revision (`-r2`, …), so `opkg upgrade` picks it up.

## How a release is made

1. The modules are built locally against the private vendor SDK tree (`package/x28-kmods/build.sh`); 38 of them come from
   unchanged Linux 4.19.205 files, 5 (`libchacha`, `libpoly1305`, `chacha_generic`, `poly1305_generic`, `chacha20poly1305`)
   from the SDK's own `crypto/` files, because the vendor kernel has the 5.x crypto library. Only built `.ko` files are
   published, never the SDK sources.
2. `tools/build/vendor_ipset.py … --kmods DIR` assembles the 224-package feed. The result is reproducible: fresh builds
   are byte-identical.
3. Before signing, `python3 tools/build/release_check.py compare --index FEED_DIR/Packages DIR` proves the feed holds the same bytes as the
   ipks the image assembly uses (the x28-* packages CI builds and the pinned module ipks), and flags a changed file with an unchanged version.
4. `tools/build/feed_release.py` refuses anything but the reviewed index (the SHA-256 pinned in the script, with the plain
   listing in [feed-index.txt](research/feed-index.txt)), signs it with the offline key and verifies the signature.
   Signing on a Mac uses `tools/build/usign/`, a container built from the exact `usign`/`libubox` commits OpenWrt 23.05 uses.
5. There is **one feed release**, marked **latest**, and it is updated in place: new packages are uploaded first, then the
   index (`Packages`, `Packages.gz`, `Packages.sig`) is replaced last, so clients switch to the new set at once. Firmware
   releases are created with `--latest=false`, so they never take that slot. The tag is only a label (it is still
   `feed-3`); the URL does not contain it. `feed-1` and `feed-2` are old and only used by older images.

The details, commands and the trust model are in [research/signed-package-feed.md](research/signed-package-feed.md).

## What has been tested, and what has not

Tested ([TESTING 46](TESTING.md#46-x28-kmods-loads-the-whole-module-list-at-boot-2026-11-08), [TESTING 45](TESTING.md#45-x28-feed-3-with-opkg-and-on-the-unit-2026-11-08), [TESTING 36](TESTING.md#36-x28-opkg-feed-on-the-unit-2026-11-02)):

- the image's own `opkg` in a container against the published URL with the key the image ships: 148 checks, 0 failures;
- all 28 module packages and the loader install (opkg needs parent directories in the package, which they now have), their module files are byte-identical to the build, 8 real consumers install from the
  official feeds, unsupported things stay refused, and the earlier hand-copied modules upgrade to the signed ones;
- on the test unit, each module loaded and was exercised (traffic shaping, tc actions and filters, bonding, iptables
  matches, netlink/raw diag, AF_ALG sockets, the ChaCha20-Poly1305 RFC 7539 test vector).
- after a reboot, `x28-kmods` loaded all 51 modules of its list by itself (about 30 s into the boot, once `x28-bootok` had reset the
  boot counter), and its retry limit refuses to load after three unfinished loads in a row (tested with a forced marker).

**Not tested:** a reflashed image that carries the longer module list (the test unit got the same script by hand); real
hardware for `nbd`, `spidev`, `cdc-acm` and USB/IP; a real IPsec tunnel with ChaCha20-Poly1305; `sch_multiq` (a virtual
device has one transmit queue) and the `text` ematch (the unit's `tc` does not know it).
