# Signed package-feed release preparation (#200)

**2026-11-01: prepared locally, not published or installed.** This is independent signing/staging tooling
for the exact four-package vendor-ipset candidate in PR #217. That PR's merge and device acceptance
remain separate requirements; this document does not assert it has merged.

## Trust and immutable assets

`tools/build/feed_release.py` pins the reviewed plaintext index and all four package SHA-256 values.
It checks that `Packages.gz` decompresses to that index, then emits canonical gzip bytes to avoid
host/Python gzip-header differences. Changed packages/indexes are refused before signing.
Updating the candidate requires a new review of these identities, not a force/override flag.

The tool signs `Packages` with an operator-supplied private usign key, immediately verifies it against
the supplied public key, and stages an exclusive new release directory. It copies only these assets:

- `Packages`, `Packages.gz`, `Packages.sig`;
- the four reviewed `.ipk` files;
- `x28-feed.pub` and `SHA256SUMS`.

Private manifests, inventories, backups and keys are never selected for staging. Validated asset bytes
are retained for staging instead of re-reading mutable input files. Signing/key-verification failures
leave no release directory. If a later filesystem copy fails, verify the complete checksum list before
using any partial output; an incomplete directory is not a release.

The committed public key is `package/x28-feed/files/x28-feed.pub`, fingerprint **`7fec994ab0d15b97`**.
Its private counterpart was generated offline and remains under ignored
`private/signing/x28-feed-20261101/`, mode 0600 in a mode-0700 directory. It is not committed,
uploaded or installed as a repository secret. Before relying on this key for a public feed, the owner
must retain a secure off-host backup; the host copy alone does not provide disaster recovery.
Only the public key belongs in images. Trust must come from the reviewed key/image, not merely a
public key downloaded beside a feed. An asset checksum list is an integrity check, not a replacement
for the usign trust anchor.

## Local preparation and validation

Requires Python 3 and a locally executable, trusted `usign` (the tests used the image's existing binary
in an offline Linux container). With the reviewed unsigned candidate and operator-owned key files:

```sh
python3 tools/build/feed_release.py \
  --feed private/research/200-ipset/candidate-3 \
  --private-key private/signing/x28-feed-20261101/x28-feed.sec \
  --public-key package/x28-feed/files/x28-feed.pub \
  --out private/research/200-signed-feed/release-NEW
python3 tools/build/test_feed_release.py
```

Five unit tests pass: allowlist-only staging, tamper refusal before signing, mismatch failure without
publishable output, compressed/plain index consistency and output-overwrite refusal. Real offline usign
successfully signed/verified the staged feed; every checksum passed. Wrong-public-key and changed-index
experiments both failed and left no release directory. No key bytes were printed. Current staged bundle:
`private/research/200-signed-feed/release-2/`; logs remain private alongside it.

## Hosting choice and remaining approval

Use **version-pinned assets on an approved existing GitHub Release** of this repository. This reuses
the existing release mechanism, needs no Pages service or new repository setting, and gives opkg a
single asset-directory URL. Do not use a moving `latest` URL or overwrite published feed assets.
For a release tag selected after the relevant code/key reviews merge, the eventual feed line is:

```text
src/gz x28 https://github.com/mralinp/zlt-x28-openwrt/releases/download/APPROVED_TAG
```

Before publication: confirm the approved release/tag and source commit, verify the staged key fingerprint,
usign signature and every checksum, and confirm no assets of those names already exist. Then upload
**only the nine assets listed above**, without `--clobber`, to that existing release. Never upload the
source directory, `private/`, an enclosing archive, the private key or a vendor firmware image.
No upload, tag creation/movement, Actions secret, automatic release-job change or repository setting
change is performed by this PR. A future automated publisher would need its own reviewed secret-handling
and publication path; this tool deliberately performs no network operation.

After upload, download from the exact public URL and independently verify signature, index and package
hashes. Only then integrate the pinned URL and this public key into the private native image under #202,
including correct package records and stale-record cleanup. Test the actual image's opkg/LuCI behavior
before any separately approved deployment. Keep the signature-checking option enabled.

**Still unverified:** public asset availability/opkg downloads, off-host key backup, image integration,
on-device package/type operations, persistence and LuCI Software. The unsigned candidate's vendor feature
limits remain; signing does not add kernel features or make the full official aggregate compatible.
