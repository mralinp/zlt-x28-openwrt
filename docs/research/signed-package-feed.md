# Signed package feed (#200)

**2026-11-02: published and working on the unit ([test 36](../TESTING.md#36-x28-opkg-feed-on-the-unit-2026-11-02)).** The feed holds 182 packages: the `kernel`
record, 178 kmod stubs and the vendor-ipset set from PR #217. A feed with only the ipset packages would
still refuse everything else that needs a kmod, such as the 28 official packages that need `kmod-tun`.

## Which stubs are in it

`kmod_stub_feed.py verify` checks the stub list against the unit itself. Of the 179 modules the stubs
need, 97 are `.ko` files on the unit. The other 82 must be built in: 77 have a `=y` option in the unit's
`/proc/config.gz`, and 5 (`l2tp_*`, whose Makefile lines the check can't read) appear in its `/sys/module`.
The kernel tree is used only to map module names to options. This shows the code is present in the
kernel, not that each feature works on this unit.

## Trust and immutable assets

`tools/build/feed_release.py` pins the reviewed plaintext index, which holds every package's SHA-256, so
the one pin freezes the whole feed. It checks that `Packages.gz` decompresses to that index and each
package matches it, then emits canonical gzip bytes to avoid host/Python gzip-header differences. Changed
packages/indexes are refused before signing. Updating the feed requires a new review of the index, not a
force/override flag.

The tool signs `Packages` with an operator-supplied private usign key, immediately verifies it against
the supplied public key, and stages an exclusive new release directory. It copies only these assets:

- `Packages`, `Packages.gz`, `Packages.sig`;
- the `.ipk` files the index names (182);
- `x28-feed.pub` and `SHA256SUMS`.

Private manifests, inventories, backups and keys are never selected for staging. Validated asset bytes
are retained for staging instead of re-reading mutable input files. Signing/key-verification failures
leave no release directory. If a later filesystem copy fails, verify the complete checksum list before
using any partial output; an incomplete directory is not a release.

The committed public key is `package/x28-feed/files/x28-feed.pub`, fingerprint **`7fec994ab0d15b97`**.
Its private counterpart was generated offline and remains under ignored
`private/signing/x28-feed-20261101/`, mode 0600 in a mode-0700 directory. It is not committed,
uploaded or installed as a repository secret. Only the public key belongs in images. Trust must come from the reviewed key/image, not merely a
public key downloaded beside a feed. An asset checksum list is an integrity check, not a replacement
for the usign trust anchor.

## Local preparation and validation

Requires Python 3 and a locally executable, trusted `usign` (the tests used the image's existing binary
in an offline Linux container). With the reviewed unsigned candidate and operator-owned key files:

```sh
python3 tools/build/feed_release.py \
  --feed private/research/200-signed-feed/candidate-4 \
  --private-key private/signing/x28-feed-20261101/x28-feed.sec \
  --public-key package/x28-feed/files/x28-feed.pub \
  --out private/research/200-signed-feed/release-NEW
python3 tools/build/test_feed_release.py
```

Six unit tests pass: staging only what the index names, refusal of a changed package, index or compressed
index before signing, mismatch failure without publishable output and output-overwrite refusal. Real offline
usign signed and verified the staged feed, and every checksum passed. The image's real opkg in a disposable
arm64 container passes `opkg_feed_test.sh` (21 checks) and `vendor_ipset_test.sh` (5 groups) against this feed.
No key bytes were printed. Current staged bundle: `private/research/200-signed-feed/release-3/`.

## Hosting

**`feed-2`** (2026-11-02, 189 assets) adds `kmod-mppe` and `kmod-crypto-arc4` stubs, so PPTP installs (#228). Images
from #230 use it. `feed-1` stays published for older images.

The feed is the separate pre-release [`feed-1`](https://github.com/mralinp/zlt-x28-openwrt/releases/tag/feed-1), with
187 assets, published 2026-11-01. It can't share an automatic `vX.Y.Z` release because those already have a `SHA256SUMS`
asset, and `scripts/release.py` only reads `v*` tags, so `feed-*` tags don't affect versions. A changed feed gets a new
tag; published assets are never overwritten. Upload one file at a time to a draft, because `gh release create` with all
the assets timed out.

```text
src/gz x28 https://github.com/mralinp/zlt-x28-openwrt/releases/download/feed-1
```

For `feed-2`, replace `feed-1` with `feed-2` in that line.

The public files were downloaded and compared byte for byte, and the image's real opkg updated, verified and installed
from that URL in a container. An encrypted copy of the private key is on the owner's USB drive, and its passphrase is
in their iCloud Drive; a test restore matched. `first_boot.py` puts this URL and key in the image (#202).

**Still unverified:** ipset set types and the kernel features behind the stubs. The vendor feature
limits remain; signing does not add kernel features or make the full official aggregate compatible.

## feed-3: the stable-URL feed (#396)

**Pinned and reviewed, not yet signed or published.** `feed_release.py` pins the index of 209 packages:
`INDEX_SHA256 = 1da26cdcc8c1c5fb4a8029767b30895573639d103a0ccb7c95d5c56ccea5a270`. The plain listing to review is
[feed-3-index.txt](feed-3-index.txt): the `kernel` record, 180 stubs, 25 packages that carry our built modules
(`1:4.19.205-x28-r1`) and the 3 vendor ipset packages. Three fresh builds gave byte-identical output.

Rebuild it (needs the built modules in `private/kmods-395/feed`, the inputs of the vendor-ipset doc, and the SDK volume for the modules):

```sh
python3 tools/build/vendor_ipset.py --upstream private/research/200-ipset/upstream.ipk \
  --library private/research/200-ipset/upstream-libipset13.ipk \
  --modules private/research/200-ipset/running-module-files.txt \
  --out private/feed-396b --kmods private/kmods-395/feed
shasum -a 256 private/feed-396b/Packages     # must equal INDEX_SHA256
```

Stable URL: the feed is published as a normal release marked latest, so images and units configure it once:

```text
src/gz x28 https://github.com/mralinp/zlt-x28-openwrt/releases/latest/download
```

Each new feed revision is a new release (`feed-4`, ...) created with `--latest`; the old ones stay as snapshots. Firmware
releases are created with `--latest=false` (`release.yml`), so they never take that slot.

**Still to do:** signing (needs a Linux `usign`; this Mac has none, and the earlier tests used the image's binary), the container
test with the image's opkg, the draft release (one asset at a time) and the `first_boot.py` change in the flasher repo.
