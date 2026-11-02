# Building TPROXY modules for the stock kernel: CRC result (#201)

**Result: no-go with CRCs; superseded.** Modules built *with* symbol versions from the source we have would be refused:
of the 35 symbols they need, 19 have different CRCs and 2 aren't exported. Tested offline on 2026-11-01.

**Update, 2026-11-02:** built without `Module.symvers`, as WireGuard was (#227), the modules have no CRCs to check and the
kernel loads them. A small `x28_udp_lookup` module supplies the 2 missing exports, and an offset comparison found no layout
difference in the functions they call. They loaded and carried Passwall2's TCP and UDP traffic on the unit
([TESTING 39](../TESTING.md#39-tproxy-and-passwall2-on-the-unit-2026-11-02), #198). That loses the kernel's own safety
check, so matching offsets and a clean run are the only evidence, as for WireGuard.

The feed in [#200](https://github.com/mralinp/zlt-x28-openwrt/issues/200) and the `dnsmasq` build in
[#203](https://github.com/mralinp/zlt-x28-openwrt/issues/203) don't depend on this. The load test in
[#204](https://github.com/mralinp/zlt-x28-openwrt/issues/204) does, and shouldn't start.

## What was compared

- **Target:** the running kernel's exported symbols and CRCs, read from the `boot_a` dump. This gave 11,606 exports.
  The table agrees with the CRCs recorded in the stock modules on 945 of 945 shared symbols, so the extraction is sound.
- **Source:** the FG360 SDK's 4.19.190 kernel, brought to 4.19.205 with upstream incremental patches. 8 files
  had rejected hunks, none in the networking code the modules need. The 13 groups of files that collide on a case-insensitive
  disk were restored from upstream 4.19.205.
- **Config:** `docs/firmware/kernel-4.19.205-x28.config` plus the 6 TPROXY and socket options as modules.
- **Build:** GCC 11 on Debian bookworm, `make -k`. 2 files failed, in sound and video code, so `vmlinux` didn't link.
  CRCs were read from the 2,814 objects with `nm`.

`Module.symvers` from the stock kernel was deliberately not used for the build. `modpost` would copy those CRCs into
the modules, and the check would pass without proving anything.

## Results

| Check | Result |
|---|---|
| All symbols compared | 4,482 of 11,794 match (38.0%) |
| Needed by the new modules: match | 14 |
| Needed: CRC differs | 19 |
| Needed: not exported by the stock kernel | 2 |

- **Differ:** `skb_copy_bits`, `sk_free`, `sock_gen_put`, `sock_edemux`, `__inet_lookup_established`,
  `__inet_lookup_listener`, `__inet6_lookup_established`, `inet6_lookup`, `inet6_lookup_listener`,
  `inet_twsk_put`, `inet_twsk_deschedule_put`, `ipv6_find_hdr`, `ipv6_skip_exthdr`, `nf_defrag_ipv4_enable`,
  `nf_defrag_ipv6_enable`, `xt_register_matches`, `xt_register_targets`, `xt_unregister_matches`,
  `xt_unregister_targets`.
- **Not exported:** `udp4_lib_lookup` and `udp6_lib_lookup`. Upstream only exports them when the TPROXY or socket
  options are on (`net/ipv4/udp.c`), and they were off in the stock build. `__udp4_lib_lookup`, `__udp6_lib_lookup` and
  `udp_table` are exported, so a patch could work around this.

Simple symbols such as `printk` and `___ratelimit` match. Symbols whose types include `struct sk_buff` or `struct sock`
don't, which points to changes in those types. CRCs can't show which fields differ.

## Why it differs

Not settled, but the source is clearly not the X28's:

- The stock config has options that appear in no Kconfig file in the SDK, including
  `CONFIG_QUECTEL_NETCARD_1`, `CONFIG_TOZED_GPIO_KEYS` and `CONFIG_DNS_TRAP_MGR`. The X28 was built from a Quectel and
  Tozed tree; the SDK is Fibocom's.
- The SDK's `skbuff.h` and `sock.h` already differ from upstream, so vendors do change these headers.

GCC 11 instead of the stock 7.5, the rejects and the 39-line config difference may account for a few CRCs. They are
unlikely to explain a mismatch this wide, but that wasn't tested separately.

## Options

| Option | Gets UDP? | Risk | Blocker |
|---|---|---|---|
| Get the exact source ([#18](https://github.com/mralinp/zlt-x28-openwrt/issues/18)), then repeat this check | Yes | Low | Depends on the vendor replying |
| xray's `tun` inbound, no new modules | Likely | Low | Passed `xray run -test` only; routing still has to be built |
| Stamp the stock CRCs on after comparing struct layouts by hand | Yes | High: a wrong offset corrupts kernel memory | Removes the safety check; needs the owner's decision |
| Own kernel ([#130](https://github.com/mralinp/zlt-x28-openwrt/issues/130)) | Yes | `risk/brick`: every vendor driver gets rebuilt | Same missing vendor source for Quectel and Tozed code |

Recommendation: try xray's `tun` inbound next, and keep the request for source open.

## Reproduce

Needs the boot dump and stock modules from `private/`, plus the SDK. With `obj-crcs.txt` from `nm -A` on the build's
objects (lines of `object symbol crc`) and `needed.txt` from `nm -u` on the 6 new objects:

```sh
python3 tools/build/kernel_crc_check.py BOOT_A.bin STOCK_MODULES_DIR obj-crcs.txt needed.txt
```

It exits 1 on no-go. With only the first two arguments, it just checks the extraction from the dump.

## Not proven

- Whether any struct layout really differs. Different CRCs mean the type descriptions differ, not necessarily the
  offsets a module uses.
- What a build with GCC 7.5 or without the rejects would give.
