# Overlay (`rootfs_data`) policy for the native image (#88)

**Decision: fresh, empty overlay. Never import the stock slot's `rootfs_data`.**

## Why

- The two captured `rootfs_data` volumes differ (A: 9 populated LEBs, B: 64) and the stock system archive
  deliberately excludes them. Their contents are unreviewed: the vendor's persisted config, its
  credentials and session state, and anything the vendor tooling or earlier experiments left behind.
- A UBIFS overlay shadows the read-only rootfs, so any inherited file could silently re-enable a service
  (`zmtk_boot_done`, `lan_mgr`, vendor init links), replace `/etc/shadow` or the Dropbear keys, or restore
  the slot-sync path that [#87](../BUILD.md#boot-path-guard-against-flash-and-other-slot-writes-87)
  removes from the squashfs. The boot-path guard checks the squashfs profile, not an imported overlay.
- It keeps the claim honest: the first boot runs exactly the audited, key-only profile.

## What is implemented

`package_ubi.py` builds an empty UBIFS (`overlay_policy: fresh empty UBIFS; no captured user data` in the
manifest), re-extracted and confirmed empty with UBI Reader in #80. No tooling copies from a captured
volume.

## Consequences and rules

- The first boot formats nothing it does not own: the overlay is a volume of our own UBI image.
- Anything wanted from the stock overlay (e.g. calibration, `nvram` data) must be identified by name,
  reviewed, and added as an explicit, hashed file in the profile. Calibration/NVRAM live in their own
  partitions, not in `rootfs_data`.
- Settings kept across a sysupgrade (#477) are the owner's own backup, not the stock overlay. The new image's
  preinit hook (`x28-user-data`) restores only an allowlist from it (`/etc/config`, passwd, group, shadow,
  `/etc/dropbear`, the uhttpd certificate, `/etc/luci-uploads`, `/etc/backup`): nothing a boot script runs or
  sources, since restored files never pass the build guard. It drops an archive with symlinks or `..` names,
  and restores only into a fresh overlay of a new image on the slot the backup was saved for. See
  [sysupgrade-design](sysupgrade-design.md).
