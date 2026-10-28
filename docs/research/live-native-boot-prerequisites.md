# Live native-boot prerequisites (#84)

Read-only device observations on 2026-10-29 after #82. No settings, switch state, slot bytes,
partitions or files were changed; no vendor initialization/upgrade helper, reboot or UART command
was executed. The router remained on stock B. Raw topology and metadata stay private under
`private/research/84-native-boot/`.

## Ethernet: current draft does not match the connected path

| Observation | Result |
|---|---|
| Ethernet driver | both `eth0`/`eth1`: `mtk_soc_eth`, `/ethernet@15100000`, compatible `mediatek,mt6890-eth` |
| `eth0` | carrier 1, operstate up; ifindex/iflink 23/23 |
| `eth1` | carrier 0, operstate down; ifindex/iflink 24/24 |
| `eth0.1/.2/.3` | up, carrier 1, parent iflink 23; all members of stock `br0` |
| Switch | read-only `swconfig list`: `switch0 - MT7531AE`; 7 ports, driver reports CPU @ 6 |
| VLAN mode | enabled |
| Currently linked external switch port | port 4, 1000baseT full duplex, PVID 3 |
| Other external switch ports | ports 0, 1, 2 and 3 report link down |
| Tagged peers | ports 5 and 6 report link up; their physical role is not inferred from carrier alone |

The active switch VLAN table is:

| VLAN ID | Port membership | External port PVID |
|---|---|---|
| 1 | `1 5t` | port 1 = 1 |
| 2 | `2 5t` | port 2 = 2 |
| 3 | `4 5t` | port 4 = 3 |
| 4 | `0 6t` | port 0 = 4 |

`/proc/net/vlan/eth0.3` confirms VID 3 on device `eth0` and nonzero RX/TX counters.
These are observed stock-state settings, **not** proof they survive a cold reset or are initialized
by the draft image. The management profile from #78 selects plain `eth1`, which has no live carrier
in this setup. Key authentication passing in a container cannot establish physical reachability.
The operator confirmed the cable is in the socket labeled **4**. With switch port 4 the only
external port reporting carrier, this correlates socket 4 with the VLAN-3 path in this setup.
No cable movement or switch reconfiguration was needed.
The candidate must not be flashed under the assumption its current `eth1` draft reaches this cable.

### Source correlation and what to implement

The live `/etc/tzscript/mt7531_eth_init.sh` matches the archive member hash
`dae619760a25daa32c9cad6fec9bba6663725f25e72d31a05a2ef6a1f2c2627f`.
In the case-preserving stock archive (`rootfs/` prefix omitted):

- `etc/tzscript/mt7531_eth_init.sh:9` checks for missing `eth0.1`–`.4`.
- Lines 11–25 reset/apply the switch, setting exactly the PVID/VLAN table observed above.
- Lines 31 and 35–38 bring `eth0` up and create those four VLAN devices.
- Lines 27 and 43–45 also write a PHY register and GPIO 24. Copying/executing the whole helper
  would introduce effects beyond a reviewed minimal switch initializer; it was **not executed**.
- Comments 3–6 describe a spare switch port and separate 2.5G PHY, including intended LAN labels.
  Those comments are design context, not a measured front-panel mapping on this unit.

The live normal network and generic switch helpers also match their archived hashes:
`etc/init.d/network` = `eb3c4a65f3fca156bb46136bf5c9066e2778cbf46da630961d847a0629d85030`,
`lib/network/switch.sh` = `861c4d4f59597505a3b9c2c96f5edce668807a3401c78262f52050aa954955bf`.
The archived `network:20,22–29` switch/netifd startup calls are commented out. The generic
`switch.sh:4–14` can load UCI switch settings, but that does not establish the actual stock owner.
The vendor `lan_mgr` process is present; filename search finds the initialization-helper path in
that native binary. This is a reference and runtime presence, not a traced execution-order proof.

The packaged #80 image has neither `/sbin/swconfig` nor `/lib/network/switch.sh`, and its generic
network script's fallback `setup_switch()` is empty. Thus merely changing its LAN device to
`eth0.3` is insufficient to guarantee switch initialization. The next implementation must add a
reviewed switch tool/library closure and one explicit early switch/netifd policy for the selected
jack, without enabling `lan_mgr`, APN setup or WAN/LAN auto-adaptation alongside it. Preserve the
no-cloning policy. Source comments and live readings must not become unreviewed hardware writes.
No early network failsafe is promised; the profile deliberately disabled generic failsafe hooks.

## Slot state: unchanged B baseline, not a switching API

Fresh `/proc/cmdline` gives `bootslot=b`, `ubi.mtd=42` and SquashFS root. The complete `/proc/mtd`
layout matches the established 51-partition order. A full read of `misc` matches its original
SHA-256 `d8a5b852d2336a8a39a3a09894797de4cd9e14b84425cc12db8d02e4f8cbc780`.
All four 16-byte records at partition offsets `0x800`, `0x40800`, `0x80800`, `0xc0800` equal:

```text
00414230ffffffff0e0001000f000100
```

The source-described slot fields remain A priority/retry/success/update = 14/0/1/0,
B = 15/0/1/0. This agrees with the booted B observation. A full private `qraw` read is byte-identical
to its original; both candidate words at offsets `0x0c` and `0x4000c` remain 2. Their consumer/slot
meaning remains unproven; raw `qraw` also contains identifiers and is not published.

Live `S99zmtk_boot_done -> ../init.d/zmtk_boot_done` remains enabled. The live script and included
helpers match the archived versions used for the [clone-path analysis](native-image-readiness.md#first-a-boot-must-preserve-stock-b):

| File | SHA-256 |
|---|---|
| `etc/init.d/zmtk_boot_done` | `2549dedeeb89f1c0ca1a340abea5f69f3ed0b7572c0a56a77138bfc7e8822812` |
| `lib/upgrade/bootctrl.sh` | `36a59e5ec91e6fc961f3e05ba809b7079a282a5a0801a7b1ad0895df849de7bd` |
| `lib/upgrade/platform.sh` | `9fd775f27bb762b26a6f12540f62e76ab2cece3bc85b33d19dd5f1ffd777f340` |

The live baseline therefore does not invalidate the known cross-slot startup hazard. A future A
image must keep its completion/clone path absent in the effective overlay; returning to B also needs
the exact retry/update state reviewed so stock repair does not unexpectedly overwrite A.

This session establishes **no supported safe slot-selection/reversal API**. No helper was called and
no record was patched. The existing recovery entry tools deliberately deny shared `misc` writes and
arbitrary `rootfs_a` images. First-A deployment needs a separate exact metadata/image operation and
reviewed reverse path; neither can be smuggled into this read-only issue as a “test.” Reset-time retry
or watchdog fallback and the relationship between `misc` and `qraw` remain unknown.

## Outcome

The read-only checks identified a concrete management-path defect in the draft and confirmed the
unchanged stock-B selection state. Proceed with **offline explicit switch-profile integration** and
an exact first-A selection/reversal plan. The already completed padding recovery test need not be
repeated. No custom flash/boot is approved, and signed-content acceptance remains unresolved (#40).
