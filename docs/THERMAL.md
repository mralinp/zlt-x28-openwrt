# Thermal: baseline and the 12 V fan

Tracked in [#46](https://github.com/mralinp/zlt-x28-openwrt/issues/46). Smart fan control from the panel is planned in
[#47](https://github.com/mralinp/zlt-x28-openwrt/issues/47).

## Result in one table

Idle load, modem on and passing traffic, readings in degrees C. The fan runs at **full speed** all the time (it has no speed control yet),
so the second column is the best case for cooling.

| Sensor (thermal zone) | No fan, 2026-10-20 | 12 V fan at full speed, 2026-10-27 |
|---|---|---|
| SoC (`soc_max`) | 65 | 46 |
| CPU core 0 (`cpu_little0`) | 65 | 44–46 |
| Modem (`md_4g`) | 65 | 46 |
| NR power amplifier (`nrpa_ntc`) | 58 | 39 |
| LTE power amplifier (`ltepa_ntc`) | 58 | 40 |
| RF (`rf_ntc`) | 59 | 41 |
| PMIC (`pmic`) | 66 | 45 |

That is about **16–20 degrees cooler** at idle load, with the fan flat out. Slowing it down will give back some of that. The kernel's thermal trip points are 85 / 95 / 115 C
(`/sys/class/thermal/thermal_zone0/trip_point_*_temp`), so the unit was never near them; the point of the fan is
margin and longevity, not avoiding a shutdown. The Quectel `ql_ntc` policy has its own, unpublished limits.

## How it was measured

- **Baseline** was read from the thermal zones on 2026-10-20 (about 04:33 UTC), with the modem registered and
  passing traffic, and no fan: `for z in /sys/class/thermal/thermal_zone*; do echo "$(cat $z/type) $(cat $z/temp)"; done`
  (values are in thousandths of a degree).
- **With the fan** the numbers come from the reboot-surviving logger from #6 (`/usr/bin/templog`, one line per
  minute in `/root/templog`, last ~200 lines kept): `ssh router 'tail -n 20 /root/templog'`.
- The modem was confirmed up when the fan result was taken: `ping 8.8.8.8` from the router answered in about 95 ms
  through the SIM.

## Readings to ignore

Some stretches in `/root/templog` from 2026-10-27 before the fan was fitted read 49–52 C. The owner reports the modem was **off**
during them, so they are not a valid baseline. Use the 65 C figure above (modem on) for comparisons.

## The fan (owner to complete)

| | |
|---|---|
| Fitted | 2026-10-27, around 19:40 local (inferred from a gap in the log and a restart at that time; owner to confirm) |
| Fan | 12 V; model, size, airflow direction and mounting: _not recorded yet_ |
| Power | _not recorded yet_: from a spare 12 V supply or the router's 12 V input, **never** from a board header or signal pin |
| Control | none: it runs at full speed whenever it has power |

**Smart-fan pin (owner, 2026-10-27):** the board has a smart-fan pin that the fan will be soldered to later. Its
location, voltage and whether it is on/off or PWM are _not recorded yet_ (#47). The stock "Smart temperature control" page
(vendor UI, `cmd 372`: off / always on / smart, threshold 50–90 C) is the firmware side of that feature; its fan-status fields
read empty on this unit today because nothing is connected to the pin.

## Not measured yet

- **With the fan on smart control or at lower speed.** The table is full speed only.
- **Under load.** All numbers are idle. Run a speed test or a sustained download and read `/root/templog` afterwards to get the
  temperature at full modem power. That is the number that decides whether the fan can be slowed or switched off.
- **Noise and dust**, and what happens if the fan stops. Nothing monitors the fan.
- **The CPU frequency cap** ([#8](https://github.com/mralinp/zlt-x28-openwrt/issues/8)) and removing the debug daemons
  ([#9](https://github.com/mralinp/zlt-x28-openwrt/issues/9)) were not applied, so none of this drop is from them.
  The abnormal-restart and TR-069-log switches that were turned off do not change heat.

## Planned

[#47](https://github.com/mralinp/zlt-x28-openwrt/issues/47): control the fan from the OpenWrt panel (on, off, or by
temperature). It needs the answers to open questions first: where the smart-fan pin is, what it outputs (voltage, on/off or PWM, tach input?),
and how the fan is powered. The stock vendor smart-temperature setting may already drive it once the fan is wired to that pin.
