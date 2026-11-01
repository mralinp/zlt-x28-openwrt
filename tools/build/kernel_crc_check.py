#!/usr/bin/env python3
"""Compare kernel symbol CRCs built from source with the ones the stock X28 kernel exports (#201).

The stock CRCs come from the kernel image in a boot partition dump, checked against the CRCs its modules recorded.
Never feed these CRCs into a module build as Module.symvers: modpost would stamp them on and prove nothing.

  kernel_crc_check.py BOOT_IMG STOCK_MODULE_DIR [OBJ_CRCS NEEDED]

OBJ_CRCS: lines of "object symbol crc" taken from `nm -A` on a kernel build's objects.
NEEDED:   symbols the new modules use, one per line ("== module" lines are ignored).
Exits 1 if a needed symbol differs or isn't exported.
"""
import pathlib
import struct
import sys
import zlib


def module_crcs(path):
    d = path.read_bytes()
    shoff = struct.unpack_from('<Q', d, 0x28)[0]
    shentsize, shnum, shstrndx = struct.unpack_from('<HHH', d, 0x3A)
    sh = lambda i: struct.unpack_from('<IIQQQQIIQQ', d, shoff + i * shentsize)
    names = sh(shstrndx)[4]
    out = {}
    for i in range(shnum):
        s = sh(i)
        if d[names + s[0]:d.index(b'\0', names + s[0])] == b'__versions':
            for off in range(s[4], s[4] + s[5], 64):
                out[d[off + 8:off + 64].split(b'\0')[0].decode()] = struct.unpack_from('<Q', d, off)[0]
    return out


def kernel_image(boot):
    raw = pathlib.Path(boot).read_bytes()
    assert raw[:8] == b'ANDROID!', 'not an Android boot image'
    size = struct.unpack_from('<I', raw, 8)[0]
    page = struct.unpack_from('<I', raw, 36)[0]
    kern = raw[page:page + size]
    return zlib.decompressobj(31).decompress(kern) if kern[:2] == b'\x1f\x8b' else kern


def stock_exports(d, known):
    """Walk the PREL32 __ksymtab around one known entry, then find the __kcrctab that runs parallel to it."""
    def name_at(entry):
        p = entry + 4 + struct.unpack_from('<i', d, entry + 4)[0]
        if not 0 <= p < len(d):
            return None
        e = d.find(b'\0', p, p + 128)
        s = d[p:e] if e > p else b''
        return s.decode() if s and all(c == 95 or c == 46 or chr(c).isalnum() for c in s) else None

    target = d.find(b'\0ipv6_find_hdr\0') + 1
    entry = next(p for p in range(0, len(d) - 8, 4) if struct.unpack_from('<i', d, p + 4)[0] + p + 4 == target)
    lo, hi = entry, entry
    while name_at(lo - 8):
        lo -= 8
    while name_at(hi + 8):
        hi += 8
    idx = {name_at(p): i for i, p in enumerate(range(lo, hi + 8, 8))}
    shared = [(n, c) for n, c in known.items() if n in idx]
    n0, c0 = shared[0]
    needle, pos, best = struct.pack('<I', c0), -1, (0, 0)
    while (pos := d.find(needle, pos + 1)) >= 0:
        if pos % 4:
            continue
        base = pos - idx[n0] * 4
        ok = sum(0 <= base + idx[n] * 4 <= len(d) - 4 and struct.unpack_from('<I', d, base + idx[n] * 4)[0] == c
                 for n, c in shared)
        best = max(best, (ok, base))
    assert best[0] == len(shared), f'CRC table agrees on only {best[0]} of {len(shared)} symbols'
    print(f'stock kernel: {len(idx)} exports, CRCs agree with stock modules on {best[0]} of {len(shared)}')
    return {n: struct.unpack_from('<I', d, best[1] + i * 4)[0] for n, i in idx.items()}


def main(argv):
    known = {}
    for ko in pathlib.Path(argv[2]).glob('*.ko'):
        known.update(module_crcs(ko))
    exported = stock_exports(kernel_image(argv[1]), known)
    if len(argv) < 5:
        return 0
    stock = {**known, **exported}
    built = {}
    for line in open(argv[3]):
        _, sym, crc = line.split()
        built[sym] = int(crc, 16)
    compared = [s for s in built if s in stock]
    same = sum(built[s] == stock[s] for s in compared)
    print(f'all built symbols: {same} of {len(compared)} match ({100 * same / len(compared):.1f}%)')
    # The new modules resolve their own exports among themselves.
    need = sorted({s.strip() for s in open(argv[4]) if s.strip() and not s.startswith('==')} & (set(built) | set(stock)))
    need = [s for s in need if not s.startswith(('nf_tproxy_', 'nf_sk_lookup_'))]
    bad = 0
    for s in need:
        state = 'NOT-EXPORTED' if s not in stock else 'no-built-crc' if s not in built else \
            'match' if stock[s] == built[s] else 'DIFFER'
        bad += state in ('NOT-EXPORTED', 'DIFFER')
        print(f'  {state:13}{s}')
    print('NO-GO' if bad else 'GO', f'({bad} of {len(need)} needed symbols are unusable)')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
