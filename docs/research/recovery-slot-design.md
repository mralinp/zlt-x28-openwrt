# Recovery slot design (#152)

Design only, 2026-10-31. Nothing was written to the device; the evidence is read-only commands on the running unit and
the verified backup. Each claim is marked **observed** or **inferred**. Building and proving it is
[#153](https://github.com/mralinp/zlt-x28-openwrt/issues/153).

## Summary

Slot B keeps everything except the contents of `rootfs_b`. That partition gets a small read-only rescue system plus a
copy of the stock SquashFS. The bootloader, kernel, modem images and signatures in B stay byte-identical, so the boot
chain sees what it already accepts on slot A: a valid `rootfs_sig` with a different SquashFS.

## Kernel: the vendor kernel already in `boot_b`, unchanged

| Option | Verdict | Why |
|---|---|---|
| Vendor `boot_b` + rescue SquashFS in `rootfs_b` | **Chosen** | Nothing in the verified chain changes. The same combination on slot A has booted through every native image (observed). |
| Vendor kernel + initramfs in `boot_b` | Rejected | Rewrites a partition LK verifies. The header has ramdisk size 0 and `CONFIG_INITRAMFS_SOURCE` is empty (observed); how LK treats a ramdisk here is untested. It gains nothing, since the kernel still needs the same flash. |
| Own kernel | Rejected | No source exists yet (#18, #130). |

`boot_a` and `boot_b` are identical, as are `rootfs_sig_a` and `rootfs_sig_b` (observed, same SHA-256 in the backup). LK
fixes the command line for B: `ubi.mtd=42 root=/dev/ubiblock0_0 rootfstype=squashfs init=/etc/preinit`, so the rescue
root must be UBI volume 0 of `rootfs_b`.

## Layout of `rootfs_b`

The partition is 64 MiB: 256 erase blocks. 240 LEBs of 253,952 bytes are usable after 12 blocks reserved for bad blocks
and the UBI layout (observed on `rootfs_a`, whose two volumes total 240).

| Volume | LEBs | Size | Content |
|---|---|---:|---|
| 0 `rootfs` | 40 | 9.7 MiB | Rescue SquashFS |
| 1 `stock_squashfs` | 124 | 30.0 MiB | Stock SquashFS, 31,274,410 bytes, SHA-256 `00216f21...` |
| unallocated | 76 | 18.4 MiB | Left free for UBI wear levelling |

It fits: the whole native SquashFS is only 7,995,392 bytes today (observed), and rescue is a subset. The stock copy
uses the same 124 LEBs as on stock.

There is no `rootfs_data`. Rescue runs on a tmpfs overlay, so **rescue itself stores nothing in B**, which removes most
of the wear and power-loss risk from the partition everything depends on. UBI can still write to it (erase-counter
headers on blank blocks, moving blocks with bitflips), so the partition's raw hash will change after a boot. Compare
volume digests, not the raw partition. Logs and settings do not survive a rescue reboot, by design.

## What rescue contains

- Busybox, `dropbear`, `dnsmasq`, `netifd`, and the flash tools the native image leaves out on purpose: `ubiformat`,
  `ubimkvol`, `ubiupdatevol`, `ubiattach`, plus stock's `dd-nand` for `misc`.
- LAN only: `192.168.70.1`, DHCP on, SSH by key. No Wi-Fi, modem, WAN or firewall. Ethernet appears to be built into the
  kernel, since no Ethernet module is loaded on the native image (inferred, to confirm with the first rescue boot).
- The authorized key and host key are baked in at build time; the image stays private like the native one.
- Three commands: `x28-install`, `x28-stock` and `x28-return`. Nothing runs them at boot, and `ab_guard` checks that for
  this profile too. All three refuse unless the command line says `bootslot=b`, so a rehearsal on A cannot format its own
  root.
- `zmtk_boot_done` is absent. `x28-bootok` is kept: it does nothing on B, and it stops the tries climbing during a
  rehearsal on A.

Because rescue has no WAN, **the OpenWrt image must already be on your computer**. Rescue cannot download one.

## Entering recovery

| Method | How | Status |
|---|---|---|
| From a working A | `x28-recovery` on slot A lowers A's priority byte from `0f` to `0d` (B is `0e`), one `misc` copy at a time with the proven `dd-nand` method and a whole-partition compare after each, then reboots. | TESTING 29 proved this method on the tries byte only, not on priority. The priority effect is **inferred** from the vendor recipe. Refuses until `x28-bootok` has finished, as both write the same `misc` blocks; that script needs a done marker for this. Writes the copy at `0xc0800` first and `0x800` last, like `x28-bootok`; stock's own order is the reverse. |
| Failed boots | The preloader adds a try on each boot of A. When they run out it should roll back to B. | **Inferred, never observed.** The limit of 7 tries is also inferred. It also needs a reset: a hang with no reset adds no tries, and watchdog behaviour is unknown. Must be drilled, see the transition. |
| Download agent + UART | Last resort. | Proven for `rootfs_a`. Not proven for `misc` (#114). `slot_session.py` guards the head of stock `rootfs_b`, so its sessions, including restore, stop once rescue is on B until those guards are updated. |
| Button | Not used. | `tz_gpio_keys` holds GPIO 18 and 19 but creates no input device (observed), and nothing shows the preloader or LK reading them. A userspace check would only work when A is alive, where `x28-recovery` already works. |

**A good slot A does not land in recovery by accident.** `x28-bootok` resets A's tries after each boot where SSH and LAN
come up, and WAN health plays no part. A's success byte stays 0 as today; it only makes the counter run, and rescue
never sets it. The remaining accident is about seven power cuts in a row, each within the first minute or two of boot.
That is harmless now: rescue changes nothing until told to, and `x28-return` (priority back to `0f`, tries back to 0, same write order) boots A. It refuses unless `rootfs_a` attaches and its `rootfs` volume is a SquashFS, so it cannot select a half-written A.

This also removes a current hazard. Stock B erases A when it boots with A's tries above 3; rescue has no such script.

## Installing OpenWrt on A

```bash
ssh x28-recovery 'cat > /tmp/image.bin' < rootfs-a.bin
ssh x28-recovery 'x28-install /tmp/image.bin <sha256>'
```

SSH over LAN is the only route. USB is wired as a device port to the preloader and TFTP adds a server for no gain.
`x28-install` then:

1. Refuses unless the unit is on `bootslot=b` and all four `misc` copies hold the boot-control magic, and stops for the
   owner if a copy is damaged. Intact copies that differ are rewritten to one value with A below B, and A is lowered if
   it is not already below, as may happen after a rollback. **Nothing touches `rootfs_a` until A is below B.**
2. Compares the file with the SHA-256 typed by the owner. This proves integrity, not origin; anyone holding the rescue
   SSH key is already trusted. RAM is not a limit: 64 MiB against about 240 MB available on the full native image.
3. Checks the image: exactly the expected size, valid UBI headers, volume names and sizes, SquashFS magic. These are the
   rules in `package_ubi.py`, reimplemented for the router, since that tool is host Python.
4. Finds the target by resolving the name `rootfs_a` in `/proc/mtd`, and refuses if it is not exactly 64 MiB. The target
   is a constant: there is no argument for it, and `rootfs_sig_a`, `boot_a` and the other A partitions are never written.
5. Writes with `ubiformat` (keeps erase counters, skips bad blocks), attaches, and compares each volume's digest with
   the image. `ubiformat` is untested on this NAND driver.
6. **Only then** writes the A record in `misc` to priority `0f`, tries 0, success 0, in a fixed order: copy at `0xc0800`
   first and `0x800` last, as `x28-bootok` does, comparing the whole partition after each. Then it reboots.

Power loss up to step 5 leaves A below B, so the unit returns to rescue and the install can be repeated.

**Power loss during step 6 is the worst case in this design.** Copies with different but intact values are benign, since
either reading finds a bootable slot. But `dd-nand` rewrites a whole erase block, so a cut can tear a copy. The preloader
contains the string `no valid slot!` and its handling of damaged copies has not been read. `misc` cannot be written over
USB (TESTING 28), so such a state may have no way back. Every `x28-recovery`, `x28-return` and install has this exposure,
as `x28-bootok` already does on a smaller scale. Disassembling the preloader's record handling offline is a gate for #153.

## Back to stock

Kept in B: `lk`, `tee`, `boot`, `md1img`, `md1dsp`, `spmfw`, `pi_img`, `dpm`, `medmcu`, `sspm`, `mcupm`, `rootfs_sig`,
`loader_ext`. Dropped: the bootable stock UBI layout in `rootfs_b` and stock B's settings overlay. Those settings exist
only in the backup afterwards.

`x28-stock` has the same checks as steps 1 and 4 above, checks the stock volume's digest, rebuilds `rootfs_a` as `rootfs` (124 LEBs, stock SquashFS) and an empty
`rootfs_data` (116 LEBs), compares, and sets A to priority `0f`, tries 3, success 0: the vendor's own recipe. Stock then
boots from A. Its `zmtk_boot_done` should copy A over B and set A successful (**inferred** from the scripts), which erases rescue and leaves
two stock slots: a full return to factory firmware, and final. The owner must type a confirmation.

The result is not byte-identical to the stock UBI image, but the signed SquashFS is. Whether stock needs anything else
from its original `rootfs_data` is to be checked against the backup and in the drill. `user_data` is not touched, so the
native overlay remains as files in stock's `/data`.

## What is lost and gained against today

| | Stock B today | Rescue B |
|---|---|---|
| A dead, no computer | Unit repairs itself to stock (inferred) and has internet | Unit waits in rescue, **no internet until you install from a computer** |
| Fallback trigger | Failed boots (inferred) | Same |
| Boot with A's tries above 3 | Erases A | Harmless |
| B written in normal use | Yes, overlay and `ab_image_sync` | Never |
| Reinstall needs the download agent | Yes | No |

The first row is a real loss and the price of the design. For a router that is your internet connection, the reply is
to keep an image on your computer. Keeping stock bootable would mean no recovery slot at all.

## Transition: stock stays until rescue is proven

1. **Confirm the dump.** Present and rechecked on 2026-10-31: `SHA256SUMS` passes for all 102 listed files, including the
   51 partitions. UART and the download agent remain the last resort.
2. **Read the preloader offline.** Slot choice, rollback, what rollback writes to the record, and damaged copies. A result
   that makes `misc` writes unsafe stops the plan here. So does a rollback that leaves A at the higher priority: stock
   derives its slot from priority, not the command line (`bootctrl.sh:263-273`), so it would act as if on A and copy
   native A over running B, and step 6 must not run.
3. **Prepare the tools.** Teach `package_ubi` and `slot_session.py` the rescue layout, and `slot_session.py` a `rootfs_b`
   spec with updated guards. The router-safety-auditor reviews them.
4. **Rehearse on A.** Flash rescue to `rootfs_a`, with stock B untouched. This proves boot, LAN, SSH, the tmpfs overlay and
   dry-run checks. Your internet is down for as long as this lasts, and `x28-bootok` must keep A's tries at 0, since stock
   B erases A above 3. Then restore native A.
5. **Prove `0d` with stock B still there.** With A's tries at 3 or below, stock B skips its repair and B has success 1,
   so A's priority can be lowered and raised with nothing erased.
6. **Observe rollback with stock B still there.** Only after step 2 passes. Set A's tries to the limit live and reboot, with
   UART on, since `x28-bootok` would reset the tries if A still boots and only UART shows that result. The expected outcome
   is that stock B's repair clones all 15 A partitions, including `lk_a`, `tee_a` and `boot_a`, and writes A's tries byte.
   The dump shows those partitions match B, so only the native image should be lost. No power cuts until the tries read 0.
   Recovery order: restore `misc` live with `dd-nand` from the booted stock B, then download-agent `restore`, then `write`,
   then select A live. `misc` is only restorable while a slot boots. Costing an image to learn this before giving up stock
   is the right trade. If rollback does not happen, rescue is still useful through `x28-recovery`, but a dead A then needs
   the download agent, and the docs must say so.
7. **Write `rootfs_b` over the download agent.** This is the point of no return for stock as a bootable slot, in its own
   PR, reversible from the dump.
8. **Drills, UART on, each result recorded:** enter by `x28-recovery` three times; reinstall A; cut power during an
   install's write to `rootfs_a`; repeat rollback; read B's tries byte across rescue boots; restore stock and confirm it
   boots, then write rescue back. After `x28-stock`, `rootfs_b` matches neither the original nor rescue, so the `rootfs_b`
   guards must accept that third state.

This changes #153: its "retiring the stock copy is a separate PR after this passes" cannot hold literally, since rescue
has to occupy `rootfs_b` to be proven there. Steps 4 to 6 prove what they can first, step 7 is the separate PR, and the
embedded stock copy plus the dump cover the gap.

## Implementation steps (#153)

1. `tools/build`: rescue profile and `package_ubi` layout with its tests; reproducible, with size and hash recorded.
2. `x28-install`, `x28-stock`, `x28-return`, `x28-recovery` for slot A and a done marker in `x28-bootok`, each with host tests on a fake `misc` and `/proc/mtd`, like
   `x28-bootok`.
3. `ab_guard` run on the rescue profile.
4. The preloader reading and tool changes: transition steps 2 and 3.
5. Transition steps 4 to 8, on the unit.

`sysupgrade` (#154) follows and can rely on rescue as its backstop.

## Not known yet

- Whether the preloader rolls back at all, at what count, and what it writes to the record.
- How it treats mixed or torn `misc` copies.
- Whether a hung kernel gets reset, without which failed boots do not count.
- Whether `ubiformat` works on this NAND driver.
- Whether the tmpfs overlay fallback works in this image.
- Whether B's tries count once A is below B. B has success 1, so inferred not. Stock resets them on each B boot, so today's
  zero proves nothing, and rescue does not reset them.
- What rollback writes to the record.
- Whether the Ethernet path needs anything from the stock daemons in rescue. It comes up from `netifd` on native.
- What stock needs in a fresh `rootfs_data`, and how `zmtk_boot_done` behaves after `x28-stock`.
