# Recovery and safety

**Use the [x28-flasher](https://github.com/mralinp/x28-flasher).** It does backup, root access, flashing and the boot-order change
with the guards built in. This page explains how recovery works and the rules behind it.

## What recovery is

There is no recovery slot. Three layers, in order:

1. **The other slot.** After 6 failed boot tries the preloader boots it by itself.
2. **The fall-back overlay.** From a slot's third boot try on, the image leaves `user_data` alone and boots with a clean
   `rootfs_data` overlay, reachable with the image's SSH key. A bad setting cannot lock you out for good.
3. **USB download mode with the flasher.** Needs a computer, a USB-A to USB-C cable and your own download agent. It can rewrite a
   slot. It **cannot** write `misc`, so it cannot reset the A/B state.

## The backup

All 51 partitions, 1,072,168,960 bytes, each with a SHA-256. Made over SSH, then verified, then re-read over USB (44 partitions
byte-identical; the 7 that differ are all written at runtime).

- It contains identity, calibration and credentials. Git-ignored, never published, never used on another unit.
- Keep a second copy offline.

## USB access, as proven

| Fact | Detail |
|---|---|
| Port | preloader `0e8d:2000`, visible for about a second after power-on |
| Cable | **USB-A to USB-C only** |
| Security | secure boot (SBC), SLA and DAA all **off** |
| Tool | mtkclient at commit `7cb40e7` with local fixes, plus the Quectel `DA_BR.bin` download agent. mtkclient's bundled agent refuses flash reads on this board |
| After any USB session | the unit stays in download mode, **no internet**, until its power is cycled |
| Procedure | start the tool first (it waits), unplug power, wait 5 s, plug in |

How the write path was proven, one step at a time: read one partition and compare; read all 51; rewrite identical bytes to an
inactive partition; write one changed 4 KiB page and restore the original; only then write a native image to `rootfs_a`.

## Safety rules (learned the hard way)

**The router is someone's internet connection.**

- One change per step. Back up the file first and check the backup is non-empty.
- Read-only by default. Ask before anything that writes flash, changes LAN/WAN, the modem mode, passwords, or reboots.
- Never put the LAN IP or netmask behind an automatic apply path.
- Never run vendor binaries with unknown flags. `sms_mgr -h` rebooted the device.
- Never enter passwords, forge sessions, or run broad `find / -exec` on the router.
- Sending an SMS or placing a call needs the owner to name the number.
- Avoid long heavy jobs on the device.

**Flash work (`risk/brick`)** requires all of:

- a full verified dump,
- UART access (for development; flasher users do not need it),
- a tested way back,
- only the inactive slot,
- the guarded sessions in the flasher's `tools/recovery/`: dry run first, a typed phrase from the owner for each step. Never edit
  those tools mid-chain; their hashes bind the receipts.

**`misc`** is changed only live, with the stock `dd-nand` byte method, after a full dump, one copy at a time, with the whole
partition compared after each write.

**The image build refuses** any image whose boot path can write flash or touch the other slot (`ab_guard`). `x28-sysupgrade` is
the one reviewed exception.

## Deploying files to a running unit (legacy overlay, or a quick test)

macOS `tar` pollutes the router with `._*` files and uid 501. Always:

```sh
cd router && COPYFILE_DISABLE=1 tar --uid 0 --gid 0 -cf - usr etc | ssh x28 'cd / && tar xf -'
ssh x28 'rm -rf /tmp/luci-modulecache /tmp/luci-indexcache'   # after Lua/LuCI changes
```

The router shell is busybox ash: no `diff`, `paste`, `setsid`, `nohup` or `scp`. Use `ssh x28 'cat > f' < local`.

## Lab setup for work that takes the unit offline

Route the LAN through another router first (used here: a second OpenWrt router with a phone hotspot as primary WAN and the X28
as fallback).

Full documents: [RECOVERY](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/RECOVERY.md),
[RECOVERY-BACKUP](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/RECOVERY-BACKUP.md),
[flash-other-units](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/flash-other-units.md),
[recovery-route-proof](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/recovery-route-proof.md).
