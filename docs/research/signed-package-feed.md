# Signed package-feed release preparation (#200)

**2026-11-02: published, not yet tested on a unit.** The feed holds 182 packages: the `kernel`
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

The feed is the separate pre-release [`feed-1`](https://github.com/mralinp/zlt-x28-openwrt/releases/tag/feed-1), with
187 assets, published 2026-11-01. It can't share an automatic `vX.Y.Z` release because those already have a `SHA256SUMS`
asset, and `scripts/release.py` only reads `v*` tags, so `feed-*` tags don't affect versions. A changed feed gets a new
tag; published assets are never overwritten. Upload one file at a time to a draft, because `gh release create` with all
the assets timed out.

```text
src/gz x28 https://github.com/mralinp/zlt-x28-openwrt/releases/download/feed-1
```

The public files were downloaded and compared byte for byte, and the image's real opkg updated, verified and installed
from that URL in a container. An encrypted copy of the private key is on the owner's USB drive, and its passphrase is
in their iCloud Drive; a test restore matched. `first_boot.py` puts this URL and key in the image (#202).

**Still unverified:** on-device package/type operations, persistence and LuCI Software. The unsigned candidate's vendor feature
limits remain; signing does not add kernel features or make the full official aggregate compatible.
