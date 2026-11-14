# Hardware

The X28 and the X28 PRO have the same specification **except Wi-Fi**.

## Specification

| | Both models |
|---|---|
| SoC | MediaTek MT6890 / T750, 4x Cortex-A55, 0.5 to 2.0 GHz, `schedutil` |
| RAM | 1 GiB; Linux sees about 628 MiB (256 MiB is reserved for modem firmware, 109 MiB shared with it, 24 MiB other firmware) |
| Flash | 1 GiB NAND, 4 KiB pages, 256 KiB erase blocks, 51 partitions, A/B slots |
| Cellular | Quectel RG500L-EU, 5G NR + LTE, a subsystem of the SoC (not USB or PCIe); 4 antennas; one nano-SIM |
| LTE bands | 1, 3, 5, 7, 8, 20, 28, 32, 38, 40, 41, 42, 43 |
| 5G bands | n1, n3, n5, n7, n8, n20, n28, n38, n40, n41, n77, n78 |
| Ethernet | 4 LAN sockets: LAN 1 is 2.5 G (Realtek RTL8226B on `eth1`), LAN 2 to 4 are 1 Gb ports of an MT7531AE switch |
| USB | one USB-C: the recovery port, and a device-mode AT serial port. No 5 V out, so no bus-powered host devices |
| Console | UART 921600 8N1, **1.8 V** logic, unpopulated 3-hole footprint on the back |
| Front panel | 3 LEDs (radio, signal quality, system); reset and WPS buttons |
| Power | 12 V DC, at least 0.7 A |
| Cooling | passive; no fan header |
| Kernel | vendor Linux 4.19.205, identical in both slots |

| Wi-Fi | X28 | X28 PRO |
|---|---|---|
| Chips | one dual-band MT7915D on PCIe | two MT7915 cards, one per band |
| Profile | one-card `l1profile.dat` | two-card profile, written by `x28-wifi-l1` when it finds two chips |
| Antennas | 4 | 8 (not confirmed) |

The PRO also has an RJ11 phone socket (a Silicon Labs SLIC); it is not driven yet.

## Flash layout

Two full slots of about 198 MiB each (`rootfs`, `boot`, `lk`, `tee`, modem images), a shared 427.5 MiB `user_data` (our overlay),
modem calibration and settings (`nvcfg`, `nvdata`, `nvram`, `protect1/2`), and identity partitions (`proinfo`, `productinfo`,
`qraw`, `seccfg`).

**Identity and calibration partitions are never written** by the flasher or by sysupgrade. They write only `rootfs_a` or
`rootfs_b`, and the priority bytes in `misc` from the running system.

## Ethernet sockets

| Socket | Port | Speed |
|---|---|---|
| LAN 1 | its own MAC (`eth1`), not behind the switch | 2.5 G |
| LAN 2 | switch port 1 | 1 Gb |
| LAN 3 | switch port 2 (by elimination, not plugged yet) | 1 Gb |
| LAN 4 | switch port 4 | 1 Gb |

LuCI's Switch page cannot show a link on LAN 1: the switch driver never reports it.

## USB-C

- **Recovery:** the preloader opens a USB window for about a second after power-on. USB-A to USB-C cable only.
- **Device mode:** `/sys/devices/platform/11201000.usb/cmode` picks the role (1 auto, 2 host, 3 device; lasts until reboot).
  With `3`, a computer sees the modem's AT serial port. The native image does not set it, so the port is idle on a computer.
- **USB Ethernet:** the kernel has RNDIS (no macOS driver). An out-of-tree NCM module worked on a Mac after a patch; the
  unpatched one panics the kernel (#488).
- **Host mode:** the controller starts but there is no VBUS supply. A self-powered device or hub is untested.

## UART

Top-left corner of the back of the board, silkscreen `TZ7.823.432 X28`. Left to right: **RX, GND, TX**.

- Logic is 1.8 V: use a level shifter. **Never drive board RX from a 3.3 V adapter.**
- For read-only capture, leave board RX unconnected.
- Users flashing with the flasher do not need a UART; development work on flash does.

## Heat

| Reading (idle, modem on, °C) | Stock, no fan | Stock, 12 V fan | Native image |
|---|---|---|---|
| SoC | 65 | 46 | about 40 |
| Modem | 65 | 46 | about 39 |
| PMIC | 66 | 45 | about 38 |

Kernel trip points are 85 / 95 / 115 °C. The native image runs cooler than stock with a fan, probably because fewer vendor
services run (not isolated; whether the fan was running for that reading is not recorded). Under load, Passwall2 at 200 Mbit/s
read 42.8 °C. A load average of about 3 on an idle CPU is three vendor kernel threads in uninterruptible sleep; it is harmless.

Not measured: sustained load without a fan.

## Not recorded yet

LAN 3's port, how switch port 0 relates to the 2.5 G socket, the PRO's board-name string and antenna count, USB host with a
powered hub.

Full documents: [MODULES](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/MODULES.md),
[HARDWARE](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/HARDWARE.md),
[THERMAL](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/THERMAL.md),
[hardware architecture](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/x28-hardware-architecture.md).
