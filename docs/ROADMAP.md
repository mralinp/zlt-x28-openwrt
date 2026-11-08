# Roadmap to a stable release

This is the plan, not the current state. For what works today see [STATUS](STATUS.md). Detail per phase: [PROJECT-PLAN](PROJECT-PLAN.md).

The target layout is simpler than today's two full firmwares:

- **Slot A: stable OpenWrt**, the thing you run.
- **Slot B: a recovery slot**, a small kernel and recovery path that can rescue the box and install or reinstall
  OpenWrt on slot A, and put the stock firmware back if you want it. This frees the flash that now holds a second
  full firmware and removes the need for the download agent and a UART in everyday recovery.

Roughly in order ([PROJECT-PLAN](PROJECT-PLAN.md) has the detail):

1. Soak and test the slot-A image: 48 h without unexplained reboots, Wi-Fi client and throughput tests, more LED
   states, the idle CPU and RAM baseline.
2. Design and build the recovery slot, including the way back to stock.
3. `sysupgrade` for the new layout.
4. A tagged stable release, the device page for the OpenWrt wiki, and build documentation for other owners.
5. Later: fan control from LuCI ([#47](https://github.com/mralinp/zlt-x28-openwrt/issues/47)), local SMS and voice
   on the native image, and a 4.19 kernel plus kmod feed built from a sibling-device SDK
   ([#130](https://github.com/mralinp/zlt-x28-openwrt/issues/130)).
