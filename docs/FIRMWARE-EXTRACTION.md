# Offline firmware extraction — 2026-10-21

Private results are under `private/firmware/20261021/` (ignored by Git). Original backups remain unchanged. Boot B and rootfs B decompressed hashes match the backup manifest.

Rootfs UBI volumes were reconstructed with UBI Reader 0.8.16. SquashFS system files were extracted with unsquashfs 4.6.1: **4333 regular files, 286 directories and 390 symlinks**, excluding /dev and xattrs. Found 90 init entries and 146 kernel module files. No live modem access or firmware execution occurred.

The authoritative tree is Docker volume `x28-rootfs-b-analysis-20261021`. The private archive `rootfs-b-system.tar.gz` preserves case-distinct names that collide on a normal macOS filesystem. Both `xt_DSCP.ko` and `xt_dscp.ko` were verified. Do not extract onto a case-insensitive filesystem for analysis.

The private archive SHA-256 is `29520a1c13927c15a842067fd99b37e513b6a785da02c9bfb84caf4653dcf958`.

The boot kernel payload was split and decompressed. Remaining boot/FDT parsing, writable UBIFS file tree and other partitions were not extracted. The original rootfs_data volume image is private; sparse layout needs filesystem-aware handling.

Extraction used a local Linux container with networking disabled, read-only input and no elevated capabilities. REA's firmware tools were not run because their provider is the macOS host; this is shell-tool evidence. The Docker tooling image is `x28-firmware-tools:local`; digest `sha256:b62d498bc2dc84ffc6ea68eaaa3512e33c8bffe644458f734c154f68ec43bf0c`. Container recipe and exact pip versions are recorded in `tools/firmware/`.

This yields installed firmware files, not corresponding source or a rebuildable image. Missing SDK/kernel inputs, native integration and proven recovery remain unresolved.
