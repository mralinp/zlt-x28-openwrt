# Boot, slots and upgrades

## Boot chain

BROM → **preloader** (picks the slot, counts a try, opens a one-second USB window) → **LK** (verifies and loads the kernel and
modem images, passes `bootslot=a|b`) → ATF/TEE → Linux.

Both slots hold the same vendor kernel. We replace only `rootfs_a` / `rootfs_b`.

## The slot record in `misc`

A MediaTek A/B record (magic `\0AB0`) at offset `0x800`, stored **four times**, one per erase block. Per slot: priority, tries,
successful.

| Rule | Detail |
|---|---|
| Which slot boots | A, unless B's priority is higher |
| Boot counter | the preloader adds one try to the selected slot on every boot |
| Fall-back | at 6 tries the other slot gets priority 15 and boots |
| Reset | `x28-bootok` writes the running slot's tries back to 0 after a good boot, in all four copies |

**Consequences to remember**

- Do not reboot a unit casually while its tries are not reset.
- Never boot stock B with A's tries above 3: stock B "repairs" A, which erases it.
- The slot's success byte is left at 0 on purpose. Stock sets it together with copying A over B, which this image never does.
- `misc` **cannot be written over USB**: the download agent never acknowledged a block write (tried on two units). It is changed
  only from the running system, with the stock `dd-nand` byte method, one copy at a time, last copy first, each read back.

## Is the rootfs signature a blocker? No

LK has a `rootfs_sig` check and prints `ROOTFS_SIG_VFY Success`, but it authenticates the `rootfs_sig` partition's metadata, not
the rootfs content. No content check was found in LK or the kernel, the preloader reports secure boot, SLA and DAA **off**, and
a rootfs we built boots. So a new rootfs needs no new vendor signature.

## Sysupgrade

`x28-sysupgrade` implements OpenWrt's `platform_check_image` / `platform_do_upgrade` for this layout.

1. **Check**, no writes: a UBI image for this board, size fits, hash matches, running slot's tries are 0.
2. **Pick the target:** always the slot that is **not** running.
3. **Write from RAM:** `ubiformat` the target, then attach it and compare the volumes.
4. **Only then** change `misc`: target priority 15, the other 14, target tries 0.
5. **Reboot.** The new image's `x28-bootok` confirms it; if it never gets there, the preloader falls back at 6 tries.

Never reset tries or flip priorities before step 3 verifies.

| Failure | Result |
|---|---|
| Check fails | nothing written |
| Write or verify mismatch, or power loss while writing | target left unselected; the old slot boots as before |
| Power loss while writing `misc` | at most one copy is mid-write; the preloader takes the first valid copy, which is written last |
| New image boots but is bad | counts to 6, falls back |
| Both slots bad | only the flasher over USB |

**The first upgrade on a freshly flashed unit replaces stock on slot B.** After that the two slots hold the new and the previous
OpenWrt. Your backup is the way back to stock.

### Signed images

OpenWrt's own scheme (`fwtool` + `ucert`), no custom crypto. Only a signed image passes on the router.

- The **feed key** stays offline. It certifies a separate **image-signer key** once (valid one year, revocable).
- Only the signer key and its certificate are in CI, in a `release-signing` environment that needs the owner's approval.
- The unsigned tarball is not published (LuCI would offer "Force upgrade" for it).

### `x28-upgrade` and the update notice

`x28-update-check` looks at GitHub for a newer **stable-form** release (`vX.Y.Z`) with a signed image; LuCI's Overview shows a
notice and an *Upgrade now* button. `x28-upgrade -y` downloads it, checks the `.sha256`, runs `sysupgrade -T`, then upgrades.
Nothing installs by itself.

### What is kept

- A settings backup holds all of `/etc/config` and `/etc/dropbear`, plus the telephony store.
- `x28-upgrade -y` keeps settings changed from the image's defaults. The backup travels through `user_data` and is restored on
  the new slot's first boot; an allowlist decides what comes back. Cron jobs, `rc.local` and other files are not kept.
- This takes effect **from the second upgrade**, because an upgrade runs the *old* image's `platform.sh`.
- Installed packages are not reinstalled; a list goes to `/etc/backup/installed_packages.txt`.

## Factory reset

The overlay is on `user_data`, which OpenWrt's own reset does not reach, so `x28-storage` ships its own `firstboot`: it marks the
volume and the next boot removes the overlay (a live overlay is never deleted).

| Way | How |
|---|---|
| Button | hold reset 10 s with the unit running. Ignored in the first 3 minutes after boot and if held at power-on |
| LuCI | System > Backup / Flash Firmware > Perform reset |
| SSH | `firstboot -y -r` |

Afterwards: empty root password, default LAN address, new Wi-Fi key and host key.

## Not proven

- The preloader's tries-6 fall-back between two native slots (never seen; the logged maximum is 5) (#458).
- An interrupted write on hardware (#458).
- LuCI's own flash page (#478).
- What a half-written slot does: panic and reset, or hang.
- No off-device way to rewrite `misc` exists.

Full documents: [BOOT-FLOW](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/BOOT-FLOW.md),
[sysupgrade-design](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/sysupgrade-design.md),
[slot-b-reuse](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/slot-b-reuse.md),
[slot-selection](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/slot-selection.md),
[overlay-policy](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/overlay-policy.md).
