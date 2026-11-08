#!/usr/bin/env python3
"""Write the plain listing of a built feed, for review before it is pinned and signed (docs/research/feed-index.txt).

  feed_listing.py --feed DIR --out FILE [--vendor ipset libipset13 x28-ipset-kernel]

Groups: the kernel record, packages that carry our modules (version `-rN`), the vendor ipset packages, and the stubs.
"""
import argparse
import hashlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import kmod_stub_feed as ks  # noqa: E402


def listing(feed):
    raw = (feed / 'Packages').read_bytes()
    idx = ks.parse_index(raw.decode() + '\n')
    vendor = ['ipset', 'libipset13', 'x28-ipset-kernel']
    built = sorted(n for n, p in idx.items() if '-r' in p['Version'].split(ks.KERNEL)[-1])
    stubs = sorted(n for n in idx if n not in built and n not in vendor and n != 'kernel')

    def row(n):
        p = idx[n]
        return f"{n:34} {p['Version']:20} {p['Architecture']:16} {int(p['Size']):>6}  {p['SHA256sum'][:16]}  {p.get('Depends', '-')}"
    out = [f'# X28 feed index review. Packages sha256 {hashlib.sha256(raw).hexdigest()}',
           f'# {len(idx)} packages: kernel, {len(stubs)} stubs, {len(built)} built modules (-r{ks.REV}), {len(vendor)} vendor ipset.',
           '# columns: package, version, architecture, size (the ipk), sha256 (first 16 hex), depends', '',
           '## kernel record', row('kernel'), '',
           f'## built modules ({len(built)}): each ipk carries its .ko files in /lib/modules/x28']
    out += [row(n) for n in built]
    out += ['', f'## vendor ipset ({len(vendor)})'] + [row(n) for n in vendor]
    out += ['', f'## stubs ({len(stubs)}): empty packages for modules the kernel already has'] + [row(n) for n in stubs]
    return '\n'.join(out) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--feed', type=pathlib.Path, required=True)
    ap.add_argument('--out', type=pathlib.Path, required=True)
    a = ap.parse_args()
    a.out.write_text(listing(a.feed))
    print('listing written to', a.out)


if __name__ == '__main__':
    main()
