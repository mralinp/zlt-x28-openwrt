# Sysupgrade for the A/B layout: design (#154)

Written as research and design before anything ran; it has since been built (`package/x28-sysupgrade`) and run on a unit ([TESTING 52 to 53d](../TESTING.md)). Inputs: [slot-b-reuse](slot-b-reuse.md) (preloader behaviour, decoded not run),
the build guard in [BUILD](../BUILD.md), and the flasher's boot-order step. Open points are marked.

## Constraints that shape it

- `misc` is written only from the running system (`dd-nand`, four copies, last first, read back). DL cannot write it, so the priority flip
  and the tries reset are sysupgrade's job, as in the flasher's *Boot order* step.
- The preloader picks A unless B's priority is higher, counts a try per boot, and at 6 tries gives the other slot priority 15 and resets.
  `x28-bootok` puts the running slot's tries back to 0 after a good boot.
- The image build **refuses** `sysupgrade`, `ubiformat`, `ubiupdatevol`, `mtd ... write`, `lib/upgrade/*` and writes to `/dev/mtd*`
  ([BUILD](../BUILD.md), `ab_guard` in x28-flasher). Sysupgrade needs a reviewed, narrow exception, not a general one.
- The slot image is a full UBI image (`rootfs` squashfs + `rootfs_data`, 126 erase blocks) for `rootfs_a`/`rootfs_b`. LK checks
  `rootfs_sig`, not the rootfs content, and no content check was found, so a new rootfs needs no new signature.
- The overlay lives on `user_data` and is reset when the image UUID changes ([overlay-policy](overlay-policy.md)). A kept config is a
  separate decision.

## Target: the slot that is not running (#509)

Every sysupgrade writes the slot the unit is **not** running (`rootfs_b` when running A, `rootfs_a` when running B), verifies it, and only
then gives it the boot priority. The running slot is never written and stays the fall-back.

| | |
|---|---|
| Runs from | RAM (the usual stage 2) |
| Backstop if the new image does not boot | Preloader goes back to the old slot at 6 tries; the old slot is untouched (not yet proven between two native slots) |
| Power loss mid-write | Old slot untouched and still selected; the new slot is half-written but not selected |

On a unit whose other slot still holds stock (native on A, stock on B), the first sysupgrade replaces stock: stock stays only until then
(x28-flasher#89), and the backup is the way back to it. Until #509 the image was written **in place** on the running slot unless
`/etc/x28-native-b` and `/tmp/x28-write-b-ok` named B; images up to v0.75.0 still do that (an upgrade runs the old image's `platform.sh`).

## Steps (OpenWrt `platform_check_image` / `platform_do_upgrade` shape)

1. **Check** (running system, no writes): the file is a UBI image for this board, its size fits the mtd, the manifest hash matches, and
   `x28-bootok` is installed. Refuse if the running slot's tries are not 0, since a counting slot is not a good base.
2. **Pick the target**: the slot that is not the `bootslot` on the command line. Read `misc`, check the magic in all four copies, and refuse
   otherwise.
3. **Write from RAM**: stop services, `ubiformat` the target mtd with the image, then verify it. *(Corrected in #457: `ubiformat` rewrites erase counters, so a whole-mtd hash cannot match; the verify attaches the result and compares the volumes. Untested.)*
   Touch nothing else and **do not touch `misc` yet**.
4. **Only then change `misc`**: target priority above the other (15 and 14), target tries 0, success untouched; four copies, last first,
   each read back.
5. **Reboot.** The new image's `x28-bootok` resets its slot's tries after a healthy boot. A boot that never gets there counts to 6 and the
   preloader falls back.

Never reset tries or flip priorities before step 3 verifies: a half-written slot with a fresh budget is the worst case.

## Who may flash

`/sbin/sysupgrade` and LuCI's flash page work once the stage 2 files are in the image, and the root password is empty until the owner sets
one. With `ucert` on the router (every image since #476) only a signed image passes OpenWrt's own check, and that signature is the
authentication. Without `ucert` no write happens unless the operator creates `/tmp/x28-upgrade-ok` on the router first (RAM, gone at reboot).

## Signing images (#476)

OpenWrt's own scheme, no custom crypto: `fwtool` appends metadata and a certificate to the image, and the router checks it with `ucert`
against `/etc/opkg/keys` (`REQUIRE_IMAGE_SIGNATURE=1` makes an unsigned image fail). The certificate chains a **separate image-signing
key** to a trusted key, so the feed key (trusted on the router) stays offline: it issues the signer certificate once
(`tools/build/image_sign.sh gen-signer`, valid one year, revocable), and only the signer key and its certificate go into CI.
`image_sign.sh sign` adds the metadata, signs and appends the certificate; `verify` does what the router does. The `ucert` ipk
(verify only) must be on the image before the check is turned on, or every upgrade would fail.

### Release flow for signed images

Since #254 the **Image** workflow (`.github/workflows/image.yml`, called by Release) builds the general image from the release's assembly
and the private stock rootfs (`mralinp/x28-vendor-inputs`, read with the `X28_INPUTS_TOKEN` secret), wraps it with the flasher's
`sysupgrade_tar.py` and attaches `x28-sysupgrade-<version>-unsigned.tar` (plus `x28-native-image.tar.gz` for the flasher; both are listed in the release's `SHA256SUMS`),
then starts Sign image. Without the secret it only warns; a tarball built locally can still be attached by hand. The manual workflow **Sign image** (`.github/workflows/sign-image.yml`) takes the tag, the
owner's SHA-256 of that file and the board names, runs in the `release-signing` environment (restrict it to `main` and require a reviewer),
signs with the image-signer secrets (`X28_IMAGE_SIGNER_KEY`, and `X28_IMAGE_SIGNER_CERT` stored base64-encoded because the ucert blob is binary), checks the result against the feed's public key as a
router does, and attaches `x28-sysupgrade-<version>.tar` and its `.sha256`. The feed key is never in GitHub.

## Failure behaviour

| Failure | Result |
|---|---|
| Image check fails (1, 2) | Nothing written. |
| Write or read-back mismatch (3) | Target left unselected; the old slot boots as before. |
| Power loss in 3 | As above. |
| Power loss in 4 | At most one `misc` copy is mid-write. The preloader takes the first copy with a valid magic, so copy 1 (written last) still says the old state until the end. |
| New image boots but is bad | Tries count to 6, preloader flips back, old slot boots. |
| Both slots bad | Loop or hang; only DL with the flasher. |

## Image format and config

- One file: a tarball in the OpenWrt sysupgrade shape (`sysupgrade-x28/root` = the UBI image, `root.sha256` its hash, `root.rootfs` = `sha256 bytes` of the squashfs in volume 0, which the verify reads back), built by the same
  tooling as the slot image, in x28-flasher's `tools/build`. No new signing: the feed key is for packages.
- Config (#477): a sysupgrade without `-n` keeps the settings; `x28-upgrade -y` runs `sysupgrade -k -u`, so only files changed from
  the image's defaults are kept (an untouched default config must not hide a newer one: images carry no uci-defaults to migrate it).
  `platform_pre_upgrade` copies OpenWrt's backup to the root of `user_data`, the overlay both slots share, as `x28-keep-<target slot>.tgz`.
  On the new image's first boot, preinit (`x28-user-data`) wipes the old overlay as before and, only then and only on that slot, passes
  an allowlist from the backup ([overlay-policy](overlay-policy.md)) to `80_mount_root` as `/sysupgrade.tgz`, OpenWrt's own restore
  (passwd/shadow merged). Any other boot deletes the file. Cron jobs, `rc.local`, scripts and other files outside the allowlist are not kept.
  - Takes effect from the second upgrade: stage 2 runs the old image's `platform.sh`, and images up to v0.78.0 have no copy step.
  - Images up to v0.78.0 also never delete the file: after a downgrade to one, a backup can wait in `user_data` until a newer image boots
    on that slot. `sysupgrade -n` from a newer image deletes it.
  - Config formats must now stay compatible from one release to the next.
  - The package list goes to `/etc/backup/installed_packages.txt`; nothing reinstalls from it yet.

## Open and untested

- Whether a half-written A panics and resets, or hangs until the watchdog; the command line has no `panic=`.
- The preloader's tries-6 branch (never seen; the logged maximum is 5).
- Whether the preloader recovers a `misc` whose copy 1 is blank (decoded as yes, not run).
- The narrow exception to the build guard, and the bumped `ab_guard`/submodule pin in x28-flasher.

## Implementation issues to open after review

1. Sysupgrade image tarball and its host checks (x28-flasher `tools/build`), no device.
2. `platform_*` hooks and the `misc` writer as a package, host-tested with a fake `misc` and writer (`risk/brick`).
3. Build-guard exception limited to that package (x28-flasher), auditor review.
4. Hardware pass on the sacrificial unit with UART: step 3 interrupted, step 4 interrupted, a bad image, the tries-6 fall-back.
