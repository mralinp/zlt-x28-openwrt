# x28-kmods

Kernel modules the vendor 4.19.205 kernel lacks, built for it from source, and `x28-kmods`, the init script that loads
them safely at boot (`files/x28-kmods.init`).

| Module | Source | Why |
|---|---|---|
| `wireguard` | `src/wireguard`: [wireguard-linux-compat](https://github.com/WireGuard/wireguard-linux-compat) v1.0.20220627 (tag tarball sha256 `7bd8ea94...36d0`), `src/` only, plus `src/x28-wireguard.patch` | WireGuard (#227) |
| `nf_socket_ipv4/6`, `nf_tproxy_ipv4/6`, `xt_socket`, `xt_TPROXY` | `src/tproxy`: unchanged files from Linux v4.19.205 (`net/ipv4/netfilter`, `net/ipv6/netfilter`, `net/netfilter`) | TPROXY for Passwall2 (#198) |
| `x28_udp_lookup` | `src/tproxy/x28_udp_lookup.c` (ours) | exports `udp4_lib_lookup`/`udp6_lib_lookup`, which the stock kernel never exported |

The patch drops wireguard-linux-compat's `ktime_get_coarse_boottime_ns()`, which the vendor tree already defines.

Build (needs the private SDK tree in the `x28-kbuild` volume, see [BUILD](../../docs/BUILD.md)):

```sh
docker run --rm -v x28-kbuild:/k -v "$PWD/package/x28-kmods:/src:ro" -v "$PWD/private/kmods:/out" \
  debian:bookworm bash /src/build.sh
```

The SDK tree and the built `.ko` files stay private: only these sources are published. A rebuild on 2026-11-02 matched
the modules on the test unit section for section (`.text`, `.rodata`, `.data`, init and exit code); the files differ
only in embedded build paths.

Licence: GPL-2.0, as each file states (`src/wireguard/COPYING`), unlike the rest of this repository.
