# Test log

A condensed view of [TESTING.md](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/TESTING.md), which has every test with
its commands and what it did **not** prove. Numbers are that document's. Start there before trusting a claim anywhere.

Units: one ZLT X28 (most tests) and one X28 PRO. One SIM, one carrier. Host: Apple Silicon Mac with Docker.

## Safety and recovery (stock firmware, slot B)

| # | Test | Result |
|---|---|---|
| 1 | Full NAND backup over SSH | ✅ 51 partitions, all SHA-256 match |
| 2 | USB recovery port at power-on | ✅ preloader `0e8d:2000`; USB-A to C only |
| 3 | Boot-security config | ✅ SBC, SLA, DAA all off |
| 4 | Download agents | ✅ only mtkclient `7cb40e7` + the Quectel agent reads flash |
| 5–6 | USB read of `lk_b`, then all 51 partitions twice | ✅ 44 match, 7 differ (all runtime-written) |
| 15 | UART console | ✅ 921600, 1.8 V; boot and recovery logs captured |
| 18 | Rootfs signed metadata vs content | ✅ offline RSA-PSS checks agree; enforcement unresolved at the time |
| 19–20 | Restore guardrails; read-only write rehearsal | ✅ 24 synthetic tests; 6/6 guarded reads |
| 21 | Identical-byte USB rewrite of an inactive partition | ✅ acknowledged, 12/12 reads match |
| 7, 22 | Changed 4 KiB page, then restore | ✅ 18/18 reads match; stock B returned |

## Feasibility (before any flash)

| # | Test | Result |
|---|---|---|
| 8–11 | Kernel config, dependency map, fw3 fit, ABI vs 23.05 | ✅ no `nf_tables`, no DSA; fw3 fits; works with 4 compat libraries |
| 12–13 | Userspace build and automatic release | ✅ 177 packages, 4.7 MB |
| 14 | musl link test of the vendor stack | ✅ 10/10 binaries resolve |
| 16 | 23.05 userspace in QEMU | ✅ 12/12: procd, netifd, fw3, ubus, LuCI |
| 17 | 23.05 userspace on the X28 in a RAM chroot on the stock kernel | ✅ 10/10; router state unchanged |

## The native image (slot A)

| # | Test | Result |
|---|---|---|
| 23 | Image written with the guarded sessions | ✅ five images; read-back and neighbour guards match |
| 24 | First boot, management | ✅ SSH, LAN, LuCI |
| 25 | 5G data | ✅ `wan` up on `ccmni1` in about 3 s |
| 26 | Services and persistence across reboot | ✅ |
| 27 | Boot counter | ✅ preloader adds a try; `x28-bootok` resets it in four copies |
| **28** | **Download-agent block write to `misc`** | ❌ not acknowledged, twice; `misc` intact |
| 29 | Live `misc` byte writes with `dd-nand` | ✅ full 1 MiB compared after every write |
| 30 | Temperature and idle load | ✅ SoC 40 °C, CPU 97 % idle |
| 33 | Soak | ✅ 26.6 h of a planned 48 h, no unexplained restart; available memory falls (#213) |
| 38 | Image with the VPN set | ✅ survives reboot |
| 51 | Two units on the v0.68.1 image | ✅ both boot, 5G/4G data on both |
| 54 | Wi-Fi LED detection | ✅ host tests; physical LED transitions not verified |

## Feed and kernel modules

| # | Test | Result |
|---|---|---|
| **32** | **TPROXY module CRCs vs the stock kernel** | ❌ 19 of 35 symbols differ; built without CRCs they load (39) |
| 34–36 | Stub feed, vendor ipset, feed on the unit | ✅ |
| 45, 47, 48 | `feed-3`, WireGuard/TPROXY as packages, `x28-kmods` as a package | ✅ up to 148 container checks, 0 failures |
| 46 | Loader after a real reboot | ✅ 51 of 51 modules at 30 s; retry limit refuses with a forced marker |
| 49 | Packaged image from the feed on two units | ✅ `x28-base` refuses removal of a member |
| 50 | Package rollback and forward | ✅ needs a downloaded ipk |

## VPN and proxy

| # | Test | Result |
|---|---|---|
| 31 | xray tunnel cost | ✅ about 0.45 cores per 100 Mbit/s |
| 37 | VPN speed | ✅ OpenVPN about 100 Mbit/s; WireGuard 715 / 330 |
| 39 | TPROXY modules and Passwall2 | ✅ TCP, UDP, IPv6 for the router and a LAN phone |
| 40 | LAN kill switch | ✅ live; clean-flash boundary untested |
| 41 | Passwall2 from a LAN client | ✅ 206 down, 40 up, CPU at most 56 % |

## X28 PRO

| # | Test | Result |
|---|---|---|
| 42 | Boot slot switched with `dd-nand` | ✅; a USB write to `misc` was refused again |
| 43 | DHCP at boot with `x28-dhcp` | ✅ served at 34 s |
| 44 | 5 GHz with the two-chip keys | ✅ no more firmware command timeouts |

## Sysupgrade

| # | Test | Result |
|---|---|---|
| 52 | Hooks on simulated NAND in QEMU | ✅ |
| 53, 53b | In-place upgrade, identical then changed image | ✅ |
| 53c | Native slot B written and booted | ✅ |
| 53d | Signed images, A → B → A cycle | ✅ |

## Telephony (2026-11-12, files copied by hand)

Poll moved 27 SIM slots into the store (6 complete messages of 2 to 8 parts, Persian text); API `200` / `401` / `400` as
designed; one short message sent and confirmed received.

## Not proven

| Area | Open |
|---|---|
| Boot | the tries-6 fall-back between two native slots; an interrupted write; any off-device `misc` rewrite |
| Upgrade | keeping settings end to end; LuCI's flash page; `x28-upgrade` and the notice have no unit test record |
| Wi-Fi | client behaviour, throughput, regulatory settings |
| Cellular | other SIMs and carriers; PIN, PAP/CHAP; long reconnect soak; `netmode` 4g/5g on a unit |
| Telephony | Persian and multi-part sending; push; the ipk; the PRO; call audio (calls connect but carry no sound) |
| System | a full 48 h soak; the falling available memory; heat under sustained load without a fan |
| Models | most features were not repeated on the PRO |
