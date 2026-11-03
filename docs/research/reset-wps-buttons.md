# Reset and WPS buttons: pins, records and boot-time behaviour

Findings for [#268](https://github.com/mralinp/zlt-x28-openwrt/issues/268), behind
[#265](https://github.com/mralinp/zlt-x28-openwrt/issues/265) (`x28-wps` fix) and
[#267](https://github.com/mralinp/zlt-x28-openwrt/issues/267) (hold-to-reset handler). 2026-11-03, native image on
slot A. Unit observations were read-only (a reader on `/dev/tz_gpio_keys`, `/sys/kernel/debug/gpio`); nothing was
flashed or rebooted, and no button was pressed while powering on. Vendor images were read offline in Ghidra; the
projects and images stay in `private/`, and this note keeps only function-level findings, no vendor code or bytes.

## Short answer

**Pressing or holding reset on the running native image does nothing, and no layer I could inspect erases flash on a
reset press.** Linux has no handler; stock's `gpiod` only restored config; LK ignores the pin; the preloader reads it only
for UART logging. It does not restore stock firmware.

## Pins and records (observed on a unit)

| Button | GPIO | `/dev/tz_gpio_keys` key | Idle |
|---|---|---|---|
| Reset | 6 | 1 | high, **low while held** |
| WPS | 7 | 2 | high (its level while held was not sampled) |

- The device tree has `tz_gpio_keys` with `gpios <6 7>` and `keys-type <1 2>`. `debugfs` shows them as `gpio-18` and
  `gpio-19` (gpiochip base 12, so pin = number - 12). Holding reset dropped `gpio-18` to `lo` for the length of the hold;
  `gpio-19` stayed `hi`. WPS's pin number follows from the device-tree order and its key 2 records, not from a level sample.
- The driver returns **12-byte reads of three 32-bit words, `[event, key, ms]`**: event 1 key-down, 2 key-up, 3 still held
  (one tick per second while pressed); `ms` is 0 on key-down and the hold time otherwise (100 ms steps on key-up).

| Press | Records |
|---|---|
| reset, taps | `1 1 0` then `2 1 N`, N = 500, 600, 900 |
| reset, 4.4 s hold | `1 1 0`, `3 1 1000` .. `3 1 4000`, `2 1 4400` |
| WPS, 3.7 s hold | `1 2 0`, `3 2 1000` .. `3 2 3000`, `2 2 3700` |
| WPS, 8.5 s hold | `1 2 0`, `3 2 1000` .. `3 2 8000`, `2 2 8500` (no cap) |

The unit kept running (no reboot, no log line, watchdog still kicked) through every press.

## Why nothing reacts on the native image

- OpenWrt's `/etc/rc.button/reset` is installed (tap reboots, 5 s hold runs `jffs2reset -y`) but button hotplug never fires:
  the kernel's input devices are only `mtk-kpd` and `mtk-pmic-keys`, no gpio-keys device.
- Stock handled the key in userspace (below); that daemon is not on this image, and the only reader seen was a leftover
  test `dd`. `x28-wps` reads the device for the WPS key only.
- Even OpenWrt's handler would not reach our overlay, which is on `user_data` ([RECOVERY.md](../RECOVERY.md)).

## Stock firmware (rootfs B, strings only)

`/usr/bin/gpiod` reads `/dev/tz_gpio_keys`. It logs a reset press at 1 s and 3 s, and on a hold of 6 s or more logs
"restore system config" and requests a reboot. The restore goes through `libcmdlib` (`util_process_system_reset`); its strings
point at file-level work (`/mnt/data/etc/tzcfg`, `/etc/tzscript/*`, flag files in `/tmp`) and show no raw partition or UBI
erase. Not disassembled.

## LK (`lk_a` dump, Ghidra)

No code references the `tz_keys_pin` or `edge_keypad` strings (they are in an embedded device-tree blob). The key code is
the MRDUMP crash-dump key through the PMIC (`mt6330_keys`). `get_boot_mode` and `get_boot_reason` are UART console commands
that print two globals with no writer in LK, so the mode is presumably handed over by the preloader. The `erase` and `gpio`
commands exist only in LK's UART shell.

## Preloader (`mtd00`, Ghidra)

GFH file at `0x40000` of the partition, loaded at `0x200ea0`, code from `0x201000`. After seeding Thumb function starts
(576 to 958 functions, 171 KB of the code region disassembled) its one GPIO input helper has exactly three callers:

| Pin | Function | Effect |
|---|---|---|
| 111 | force-download check | waits for a download host with a timeout |
| 6 (reset) | UART log setup | if the pin reads 1 and `raw_log` is 0, clears a UART flag ("Rawdata disble uart") |
| 136 | one-time read | logs "Read gpio 136 error" on failure |

Pin 7 is never read. `mtk_kpd_gpio_set` zeroes its pin tables on this board. The boot-mode strings (factory, META) follow
boot arguments and the PMIC power key. No erase or format call on these paths. So holding reset while powering on at most
keeps UART raw data on.

## Not covered

- BROM and anything before the preloader; a hold-at-power-on test on a unit (the trace says it is harmless, nothing proves it).
- Ticks past 8.5 s, and a reset hold past 4.4 s (assumed the same as WPS).
- Stock `gpiod` and `libcmdlib` beyond their strings.
- The WPS press that gave two record pairs (likely a second tap).
