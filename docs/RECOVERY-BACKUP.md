# Complete partition recovery inputs — 2026-10-21

## Prepared and verified

All **51 original partition captures** from 2026-10-20 were decompressed and checked for exact recorded byte length and SHA-256. Total main data: **1,072,168,960 bytes**. The set includes preloader/bootloader, both A/B slots, signatures, modem images, NV/calibration and configuration/user-data partitions.

Private directory: `private/recovery/20261020-capture-prepared-20261021/`

- `images/`: 51 uncompressed per-partition `.bin` files.
- `original-compressed/`: preserved original gzip captures.
- `metadata/`: original manifest, partition listing, mounts/boot records, acquisition script and a later geometry sample.
- `verified-manifest.json`, `SHA256SUMS`: verification records.
- `complete-captured-partitions.tar`: backup container holding original compressed captures and core metadata; every partition member was hash-checked after archiving.
- `ARCHIVE.sha256`, `RECOVERY-LIMITS.md`: archive integrity and limitations.

The added acquisition script and later geometry sample are loose metadata added after the archive was made; they are not archive members. Original backup files remain unchanged. The entire private tree is ignored by Git. No flash, erase, reset or reboot was performed.

## What this does NOT prove

This is the complete recorded **partition main-data set**, not a physical-chip clone, sysupgrade/factory image or a proven vendor-flasher package. No concatenated image or flash script was created. Filesystem extraction is a separate analysis product and does not make partition captures more flashable.

The installed nanddump help confirms the capture command `nanddump --bb=padbad -q /dev/mtdN` omits OOB by default, uses ECC and substitutes FF for bad blocks. A later read-only sample of MTD0/29/42/48/50 reported 4096-byte pages, 64-byte OOB, 262144-byte eraseblocks, zero reported bad blocks and no ECC failures in those sampled partitions. This is not a complete capture-time bad-block map. See the [upstream nanddump implementation](https://raw.githubusercontent.com/sigma-star/mtd-utils/master/nand-utils/nanddump.c) for format distinctions.

Several captured writable partitions were YAFFS2. Required tags may be stored in OOB or vendor in-band form; this board's layout has not been established. [YAFFS documentation](https://yaffs.net/sites/default/files/downloads/HowYaffsWorks.pdf) describes those alternatives. Hashes prove preservation of captured bytes, not filesystem consistency or recovery compatibility. The original capture read mounted writable filesystems sequentially without freeze/snapshot.

## Before relying on recovery

1. Establish UART/USB/bootloader recovery access on this hardware revision.
2. Determine the supported restore transport, absolute partition map and NAND-aware handling of ECC/OOB/bad blocks, security metadata and slot selection.
3. Resolve YAFFS tag placement and live-filesystem consistency; obtain any missing data through a separately documented, appropriate capture process.
4. Test a restore on recoverable spare hardware and verify boot, modem, Wi-Fi, identity and calibration.
5. Keep a second private copy on separate storage. Never publish or use another unit's NV/calibration partitions.

**Do not upload these raw partitions to LuCI or flash them blindly. A tested recovery path remains the blocking requirement before experimental firmware flashing.**

## USB recovery probe — 2026-10-21

Two power cycles with the external USB-C port cabled to a MacBook (second run: known data cable, direct to the Mac). A 50 ms `ioreg` poll on the Mac saw **no new USB device** in either run: no MediaTek BROM/preloader port (`0e8d:*`), no Quectel gadget (`2c7c:7003`).

Router side (read-only): the Linux gadget pulled up D+ from 24.7 s to 26.5 s after boot (`mtu3_gadget_pullup on/off`) and the Mac still saw nothing, so this port/cable path carried no USB data in either boot stage. After boot `/config/usb_gadget/g1/UDC` is empty and the UDC state is `not attached`. The `VBUS_VALID` log line follows `usb.init` forcing `cmode=3` and is not evidence of a host. The firmware type is `usr`, so `usb.init` skips `adbd_usb`. `switch_otg_daemon` (Quectel) switches `cmode` between host and device modes based on `iddig_state`; `start_usb.sh` waits for a modem-side "MD USB enumeration" flag before binding the UDC.

Not yet tried: holding a button during power-on, the board's internal USB/test points, or UART (`console=ttyS0,921600n1`). The USB-C port may be power-only or not routed to the SoC on this enclosure; this is unverified. **USB recovery access remains unproven.**

Mac side, same windows: the kernel log has no USB-C port attach, accessory-security or authorization event (`log show --info --debug`, IOAccessoryManager/Port-USB-C, LDCM noise excluded), so the Mac's "Allow accessory" check never ran. Leading hypothesis (unverified): the X28 USB-C port lacks CC pull-down resistors, so a USB-C host (Mac) never sees an attach or enables VBUS over a C-to-C cable. Next test: a USB-A-to-C cable from a USB-A host port, which supplies VBUS without CC.

Offline string scan of the captured preloader (mtd0) and lk_b (mtd38), no execution:
- Preloader has MediaTek USB download and emergency-download paths ("download keys are pressed", "Force download mode", "emergency download mode(timeout)") and checks the PMIC for a cable first ("PMIC not dectect usb cable!"). Without VBUS it skips USB, consistent with the C-to-C result above.
- Preloader carries Quectel A/B boot control (`bootctrl/2.0/ab_bootcheck.c`: tries_remaining, rollback_slot, "no valid slot"). `misc` holds four copies of a `\0AB0` record; its bytes `0e 00 01 00` / `0f 00 01 00` *look like* slot A priority 14 and slot B priority 15, both marked successful. That field layout is a guess, not decoded.
- The LK device tree names a `fusb304` Type-C controller and the router lists `3-004e usb_type_c` on I2C with **no driver bound**, alongside other reference-design nodes (touch, LCD bias, sensors). Whether the chip is fitted is unknown. I2C was not probed.

### Result with a USB-A-to-C cable — 2026-10-21

**Confirmed:** with a USB-A-to-C cable from a USB-A hub port, a power cycle enumerates on the Mac:
- `0e8d:2000 "MT65xx Preloader" / MediaTek` as `/dev/cu.usbmodem11301`, about 13 s after the watcher started, present for **~1.15 s**. This is the MediaTek preloader USB handshake window.
- `2c7c:7003 "RG500L-EU" / Quectel`, serial `0123456789ABCDEF`, for ~1.7 s at kernel ~24.5–26.5 s (gadget pullup on/off), then disconnected by firmware.

So the C-to-C failure was the cable/CC path, not the board. No tool talked to either port. Security state (SBC/SLA/DAA), whether the preloader or BROM accepts a download agent, and NAND read/write support remain untested.

### Preloader security check — 2026-10-21

`mtk gettargetconfig --skipwdt` (mtkclient v2.1.4.1, commit `5a863ee`, isolated venv; `fusepy` removed because macOS has no libfuse). Code path reviewed first: handshake plus read-only preloader commands; no DA upload, no crash to BROM, no flash access, watchdog untouched.

- Connected in **preloader** mode ("regular mode"): CPU MT6880/MT6890, hw code `0x992`, subcode `0x8a00`, hw ver `0xca01`, sw ver `0x1`.
- **Target config `0x0`: SBC, SLA, DAA, root cert, mem read/write auth all disabled.** Unsigned download agents should be accepted; not yet tested.
- After the handshake the device stays in the preloader (no boot, router offline) until power-cycled.
- ME_ID was read; it is kept only in the private probe log, not here.

Still unproven: a DA that drives this board's NAND (mtkclient NAND support on MT6890 is untested here), reading a partition and comparing it with the backup hash, BROM entry if the preloader itself is damaged, and any write/restore.
