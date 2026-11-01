# Vendor-ipset dependency packaging (#200)

## Result and scope

**2026-11-01: local candidate only.** Clean dependency resolution works in the image's real `opkg`
in a disposable arm64 container. No router packages, keys, feeds, firewall state or firmware were changed.
This follows #206's removal of incomplete official-aggregate stubs.

The live router has 16 `ip_set*.ko` files, `xt_set.ko` and the supporting `nfnetlink` / `x_tables` files.
`ip_set_hash_ipmac.ko` is absent even though the recovered configuration requests it. A configuration
option alone therefore does not establish an installed capability. Runtime operation of all types is untested.
The official `kmod-ipt-ipset` aggregate must remain unavailable; this work does not claim to supply it.

Both official `ipset` **and `libipset13`** depend on that aggregate. Correcting only the utility leaves
its library's transitive dependency unsatisfied; real-opkg testing reproduced that failure.

## What the candidate contains

The released feed adds the kmod stubs to these four packages; see the [signed-feed preparation](signed-package-feed.md).

| Package | Contents / dependency |
|---|---|
| `kernel` | File-free record for `1:4.19.205-x28`; changes no kernel code. |
| `x28-ipset-kernel` | File-free record for the explicitly observed vendor subset, depending on that kernel record. Description states `hash:ip,mac` is unavailable. No `Provides: kmod-ipt-ipset`. |
| `libipset13` | Official payload and maintainer scripts, with version `1:7.17-1-x28-1` and the aggregate dependency replaced by `x28-ipset-kernel`. |
| `ipset` | Official payload and maintainer scripts, same X28 version, depending on the explicit subset and exact matching X28 library version. |

The missing type is **`hash:ip,mac`**; the differently named **`bitmap:ip,mac`** module is present.
Neither package record loads modules or adds features. Other applications explicitly requiring the
complete official aggregate still fail; adapt their packaging only after reviewing their actual requirements.

`tools/build/vendor_ipset.py` pins the two official 23.05.5 packages by SHA-256, checks their original
metadata and the supplied observed module-file inventory, preserves each compressed data archive
byte-for-byte and preserves maintainer-script contents/modes. It writes a new output directory and
refuses unknown packages, missing required inventory names and an existing output directory.
The inventory is an observation supplied by the operator, not automatic hardware attestation.
The version epoch keeps ordinary feed updates from replacing these variants with the incompatible metadata.

| Official input | SHA-256 |
|---|---|
| `ipset_7.17-1_aarch64_generic.ipk` | `df8a2a483104b8ea5fd544e8feac78b220128ae4703851c8d80d88927ebff5bf` |
| `libipset13_7.17-1_aarch64_generic.ipk` | `6965342a8d2170b34992cfea8fc5dde460253b6143d5908af1bbfa456f9a4809` |

These inputs come from the official [23.05.5 base feed](https://downloads.openwrt.org/releases/23.05.5/packages/aarch64_generic/base/).
The builder downloads nothing, executes no package scripts and contacts no router. Its output remains
unsigned; the integration test signs a disposable copy with a temporary key. No private signing key is committed.

## Reproduce locally

Download the two pinned packages to a private directory. Save a read-only inventory of this unit's
`/lib/modules/4.19.205/*.ko` filenames; do not substitute the sibling SDK's list. From the repository root:

```sh
python3 tools/build/vendor_ipset.py \
  --upstream private/research/200-ipset/upstream.ipk \
  --library private/research/200-ipset/upstream-libipset13.ipk \
  --modules private/research/200-ipset/running-module-files.txt \
  --out private/research/200-ipset/candidate-NEW
python3 tools/build/test_vendor_ipset.py
# Arm64 Docker host; both inputs mounted read-only, no host networking or NET_ADMIN capability:
docker run --rm --cap-add MKNOD \
  -v "$PWD/private/build/native-management-190b:/in:ro" \
  -v "$PWD/private/research/200-ipset/candidate-NEW:/feed:ro" \
  -v "$PWD/tools/build:/t:ro" debian:stable-slim bash /t/vendor_ipset_test.sh
```

## Validation and next device gate

Four unit tests pass: metadata/payload/script preservation, unknown-source refusal, missing-module
refusal, and complete indexed-package checksums/subset boundaries/output overwrite refusal.
The disposable fixture removes foreign-architecture stock package records, as in the existing #206
test; this does not implement #202's clean-image database integration.
The real-opkg integration passes five groups: reject an invalid signature, accept a valid signed update,
install the vendor dependency chain, refuse the unsupported aggregate without foreign modules,
and remove/reinstall the utility. No `--nodeps` or dependency forcing is used.
Independent comparison of the actual official/candidate archives also found identical payloads and
unchanged executable maintainer-script modes. The utility payload contains only `/usr/sbin/ipset`;
the library payload's regular file is `/usr/lib/libipset.so.13.4.0`.

**Still open:** persistent feed hosting/signing, image integration (#202), real kernel type/functionality
checks, LuCI Software, and on-device install/remove/persistence. The container does not use the router's
kernel and cannot prove its ipset capabilities. Nothing here closes #200's on-device acceptance criterion.

**2026-11-02:** hosting, image integration, on-device install/remove/persistence and LuCI Software are now done: see
[test 36](../TESTING.md#36-x28-opkg-feed-on-the-unit-2026-11-02). Real kernel type/functionality checks remain open.

A host-side read-only backup of the current package database/control files and affected payloads was
captured and verified (1,077,760 bytes). Both installed regular-file payload hashes match upstream.
Stale `kernel.control`, `kernel.list` and `kernel.prerm` files already exist even though no kernel
package is installed; retain them in rollback, rather than deleting them as newly added files.

Before an on-device package test, review and approve an exact candidate/command list, capture and verify
backups of the package database/control files and affected utility/library files, and prepare an exact
restore procedure. Compare the current installed payloads with these upstream payloads first; do not
assume they match. Keep feed/key changes and firewall/set operations out of the initial metadata test.
`CLAUDE.md` requires approval before device flash/configuration changes; merging this PR authorizes no
package deployment, networking change or reboot. No rollback is needed for the local test artifacts.
