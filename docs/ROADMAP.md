# Roadmap

This is the plan, not the current state. For what works today see [STATUS](STATUS.md). Detail per phase: [PROJECT-PLAN](PROJECT-PLAN.md).

The layout:

- **Slot A: OpenWrt**, the thing you run.
- **Slot B: stock firmware**, the automatic fall-back, until the first `sysupgrade`: an upgrade writes the slot that is not
  running, so the two slots then hold the new and the previous OpenWrt. There is no recovery slot (#152, #153 closed): recovery is the
  [x28-flasher](https://github.com/mralinp/x28-flasher) over the download-agent mode, which needs a computer, USB and your
  own download agent ([slot-b-reuse](research/slot-b-reuse.md)).

## Done

1. Soak and test of the slot-A image.
2. `sysupgrade` for the A/B layout, with signed images.
3. Stable release: v1.0.0.

## Next

1. **`x28-telephony`**: a package for SMS and VoIP calls on the native image (replaces "SMS and voice are not supported yet").
2. **Factory reset** back to the image defaults.
3. **OpenWrt 25.12.6 with kernel 6.12.6**, replacing 23.05.5 and the vendor 4.19.205 kernel. This is the old kernel-and-kmod-feed
   goal ([#130](https://github.com/mralinp/zlt-x28-openwrt/issues/130)); it needs a flash with brick risk and a new package feed.

Still open from earlier phases, not yet re-checked: keeping settings across `sysupgrade`
([#477](https://github.com/mralinp/zlt-x28-openwrt/issues/477)), LuCI's flash page ([#478](https://github.com/mralinp/zlt-x28-openwrt/issues/478)),
the interrupted-write hardware pass ([#458](https://github.com/mralinp/zlt-x28-openwrt/issues/458)), the OpenWrt wiki device page, build documentation for other
owners and fan control from LuCI ([#47](https://github.com/mralinp/zlt-x28-openwrt/issues/47)).
