# Native image completeness (#89)

Offline review of what the packaged candidate needs beyond files. Nothing was run on the router; the
candidate stays **NOT-FLASHABLE**.

## `/dev` (fixed in this change)

The stock kernel has `# CONFIG_DEVTMPFS is not set` ([config](../firmware/kernel-4.19.205-x28.config)).
The stock SquashFS therefore ships a static `/dev/console` (`crw------- 5,1`) and nothing else, and both
the stock and the 23.05 `procd` mount `tmpfs` on `/dev` and fill it from sysfs uevents (`udevtrigger`,
no `devtmpfs` string in either binary). Our candidate's `/dev` was an empty directory, so the kernel
would have had no initial console. `package_ubi.py` now passes `-p 'dev/console c 600 0 0 5 1'` to
`mksquashfs` and fails if `unsquashfs -ll` does not list that node. Observed on the private
`native-ubi-89` build (SquashFS digest `ebebcaf8...`, 31+13 LEBs): `crw------- root/root 5, 1 ... dev/console`.

## Kernel features the 23.05 userland relies on (config read, nothing booted)

Present: `TMPFS`, `PROC_FS`, `SYSFS`, `UNIX98_PTYS` (devpts for SSH shells), `OVERLAY_FS`, `SQUASHFS_XZ`,
`UBIFS_FS` (LZO/ZLIB), `MTD_UBI_BLOCK` (root on `/dev/ubiblock0_0`), `INOTIFY_USER`, `EPOLL`, `SIGNALFD`,
`TIMERFD`, `EVENTFD`, `VLAN_8021Q`, `BRIDGE`, `SWCONFIG`, `IPV6`, `CGROUPS`.
Absent: `NAMESPACES`, `SECCOMP` (procd jails/seccomp unusable: no enabled service needs them),
`FHANDLE`, `NETLINK_DIAG` (`ss`). `NF_CONNTRACK` is a module (relevant to the later firewall, not the
management profile).

## Decisions

- **Extra-IPK ownership:** `alsa-lib` and `libstdcpp6` files are present but have no opkg control/status
  records, and the vendor binaries that need them are not started by this profile. They are unowned files;
  `opkg` is not part of the management image's job. Adding records is deferred until a vendor service
  is enabled.
- **xattrs:** `mksquashfs -no-xattrs` is intentional; nothing in the profile needs capabilities.

## Not verifiable before a hardware boot

procd/overlay behavior with the real `rootfs_data` UBI volume (`mount_root` finding `/dev/ubi0_1` through
procd's udev pass), Dropbear's UCI service start and the key login on the real network path. QEMU cannot
run this vendor kernel. The existing QEMU test covers the 23.05 userspace on a different kernel only.
These are the first things to read from the UART log on a first boot.
