# Roadmap to a stable release

This is the plan, not the current state. For what works today see [STATUS](STATUS.md). Detail per phase: [PROJECT-PLAN](PROJECT-PLAN.md).

The target layout:

- **Slot A: stable OpenWrt**, the thing you run.
- **Slot B: stock firmware**, the automatic fall-back. There is no recovery slot (#152, #153 closed): recovery is the
  [x28-flasher](https://github.com/mralinp/x28-flasher) over the download-agent mode, which needs a computer, USB and your
  own download agent ([slot-b-reuse](research/slot-b-reuse.md)).

Roughly in order ([PROJECT-PLAN](PROJECT-PLAN.md) has the detail):

1. Soak and test the slot-A image: 48 h without unexplained reboots, Wi-Fi client and throughput tests, more LED
   states, the idle CPU and RAM baseline.
2. `sysupgrade` for the A/B layout.
3. A tagged stable release, the device page for the OpenWrt wiki, and build documentation for other owners.
4. Later: fan control from LuCI ([#47](https://github.com/mralinp/zlt-x28-openwrt/issues/47)), local SMS and voice
   on the native image, and a 4.19 kernel plus kmod feed built from a sibling-device SDK
   ([#130](https://github.com/mralinp/zlt-x28-openwrt/issues/130)).
