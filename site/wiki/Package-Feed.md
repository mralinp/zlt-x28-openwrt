# Package feed

A normal signed `opkg` feed, valid for **this device line only** (MT6890, vendor kernel 4.19.205, OpenWrt 23.05.5 userspace).

```text
src/gz x28 https://github.com/mralinp/zlt-x28-openwrt/releases/download/feed-3
```

Signing key fingerprint: **`7fec994ab0d15b97`** (`/etc/opkg/keys/7fec994ab0d15b97`). Do not turn signature checking off.

## The problem it solves

The official 23.05 feeds have about 10 000 userspace packages, which run here as they are, and 976 `kmod-*` packages built for
kernel 5.15, which can never load on 4.19.205. The feed makes `opkg` tell the truth about this kernel:

| In the feed | Count | Meaning |
|---|---|---|
| `kernel` record | 1 | marks the running kernel as installed so dependencies resolve |
| Stubs | 180 | empty `kmod-*` packages for modules the kernel already has |
| Built modules | 28 | `kmod-*` packages with modules the kernel lacks, built for it |
| Vendor ipset | 3 | `ipset` and its library for the vendor kernel's set types |
| `x28-*` | the rest | [our packages](Packages.md) |

A package that needs a module the feed has neither stubbed nor built **is refused with a clear error**. That is by design.

## Coverage of the 976 official kmods

| | Count | Examples |
|---|---|---|
| Install | 208 | WireGuard, TPROXY and socket matching, SQM and `sch_cake`, `tc-full`, `veth`, `macvlan`, `bonding`, `nbd`, `usbip`, ChaCha20-Poly1305, `cdc-acm` |
| Buildable, not built | about 190 | drivers for hardware this SoC does not have; added on request |
| Need a kernel change | 578 | `nftables`/`firewall4`, `ksmbd`, Bluetooth, `cfg80211`, namespaces |

24 of the 27 kmods that some user package depends on are covered.

## Using it

A running unit whose feed line still says `releases/latest/download` (or `feed-2`) must be switched. Since v1.0.0 "latest" is a
firmware release, which has no package index.

```sh
ls /etc/opkg/keys/7fec994ab0d15b97
sed -i 's|^src/gz x28 .*|src/gz x28 https://github.com/mralinp/zlt-x28-openwrt/releases/download/feed-3|' /etc/opkg/customfeeds.conf
opkg update
```

`opkg` may print `cannot find dependency kernel (= 5.15…)` while installing. It refers to the official record it is ignoring;
the install continues.

## How modules load

- Built modules live in `/lib/modules/x28/`, out of reach of the kernel's on-demand `modprobe`. Otherwise the first TPROXY rule
  would load them before the boot counter is reset.
- Each module package ships a list in `/etc/x28-kmods.d/`. `x28-kmods` loads them about 30 s after boot, after `x28-bootok`.
- Three unfinished loads in a row stop the loader, so a bad module cannot cause a boot loop.
- 51 modules load on the test unit.

Why modules built without symbol CRCs load on a `MODVERSIONS` kernel:
[kernel-module-crc](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/kernel-module-crc.md).

## How a feed release is made

1. Modules are built locally against the private vendor SDK tree (`package/x28-kmods/build.sh`). Only built `.ko` files are
   published, never SDK sources.
2. `tools/build/vendor_ipset.py --kmods DIR` assembles the feed. Builds are byte-reproducible.
3. `tools/build/release_check.py compare` proves the feed holds the same bytes as the ipks the image uses.
4. `tools/build/feed_release.py` refuses anything but the reviewed index (its SHA-256 is pinned in the script), signs with the
   **offline** key and verifies.
5. `feed-3` is updated in place: packages first, the index last.

## Not tested

Real hardware for `nbd`, `spidev`, `cdc-acm` and USB/IP; a real IPsec tunnel with ChaCha20-Poly1305; ipset set types in use.

Full documents: [PACKAGE-FEED](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/PACKAGE-FEED.md),
[signed-package-feed](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/signed-package-feed.md),
[kmod-gap](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/kmod-gap.md).
