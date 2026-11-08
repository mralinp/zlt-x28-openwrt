#!/usr/bin/env python3
"""One set of .ipk files per release, used by both the image assembly and the signed feed (#419).

  x28      build the x28-* packages of package/x28-packages.ini (no SDK, CI does this)
  pin      list the SDK-built packages (module packages and the loader) of a feed dir as `sha256  file` lines
  fetch    check a dir of those files against the pin list (what release.yml does after downloading them)
  kmods    unpack the .ko files of the module packages for first_boot.py --kmods (until the flasher reads ipks, #420)
  compare  check that a feed index and a dir of ipks hold the same bytes for every package of ours
"""
import argparse
import hashlib
import io
import pathlib
import shutil
import sys
import tarfile
import tempfile
import urllib.request

import kmod_stub_feed as feed

ROOT = pathlib.Path(__file__).resolve().parents[2]
PINS = ROOT / 'package/x28-kmods/ipk.sha256'


def sdk_built():
    """Names of the packages built against the private SDK tree: the module packages and the loader."""
    names = [l.split('|')[0].split()[0] for l in feed.REAL.read_text().splitlines() if l.strip() and not l.startswith('#')]
    return names + ['x28-kmods']


def ours():
    return set(sdk_built()) | {p[0] for p in feed.read_packages()}


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def pin(feed_dir):
    index = feed.parse_index((feed_dir / 'Packages').read_text() + '\n')
    return ''.join(f"{index[n]['SHA256sum']}  {index[n]['Filename']}\n" for n in sorted(sdk_built()))


def check_pins(directory, pins=PINS):
    """Every pinned file is there with the pinned hash (and nothing else of ours is trusted)."""
    bad = []
    for line in pins.read_text().splitlines():
        want, name = line.split()
        p = directory / name
        if not p.exists():
            bad.append('missing ' + name)
        elif sha(p) != want:
            bad.append('differs from the pin: ' + name)
    return bad


def read_index(source):
    text = (urllib.request.urlopen(source).read() if '://' in source else pathlib.Path(source).read_bytes()).decode()
    return feed.parse_index(text + '\n')


def compare(index, directory):
    """Differences between a feed index and the ipks of a release, for the packages of ours only."""
    bad, mine = [], ours()
    files = {p.name: p for p in directory.glob('*.ipk')}
    for name, e in sorted(index.items()):
        if name not in mine:
            continue
        f = files.pop(e['Filename'], None)
        if f is None:
            bad.append(f'in the feed, not in the release: {e["Filename"]}')
        elif sha(f) != e['SHA256sum']:
            bad.append(f'same file name, different bytes (bump the release number): {e["Filename"]}')
    for name in sorted(files):
        bad.append(f'in the release, not in the feed: {name}')
    return bad


# The eight modules every image carries (#248): WireGuard and Passwall2's TPROXY set.
IMAGE_KMODS = ('kmod-wireguard', 'kmod-ipt-tproxy', 'kmod-ipt-socket')


def unpack_kmods(directory, out):
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for ipk in sorted(i for k in IMAGE_KMODS for i in directory.glob(k + '_*.ipk')):
        with tarfile.open(fileobj=io.BytesIO(ipk.read_bytes()), mode='r:gz') as outer:
            data = outer.extractfile('./data.tar.gz').read()
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as inner:
            for m in inner:
                if m.name.endswith('.ko'):
                    (out / pathlib.Path(m.name).name).write_bytes(inner.extractfile(m).read())
                    n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    x = sub.add_parser('x28')
    x.add_argument('--out', type=pathlib.Path, required=True)
    p = sub.add_parser('pin')
    p.add_argument('--feed', type=pathlib.Path, required=True)
    f = sub.add_parser('fetch')
    f.add_argument('dir', type=pathlib.Path)
    k = sub.add_parser('kmods')
    k.add_argument('dir', type=pathlib.Path)
    k.add_argument('--out', type=pathlib.Path, required=True)
    c = sub.add_parser('compare')
    c.add_argument('--index', required=True, help='a Packages file or URL')
    c.add_argument('dir', type=pathlib.Path)
    a = ap.parse_args()
    if a.cmd == 'x28':
        with tempfile.TemporaryDirectory() as t:
            feed.build([], pathlib.Path(t), packages=feed.read_packages())
            a.out.mkdir(parents=True, exist_ok=True)
            names = ours()
            for ipk in pathlib.Path(t).glob('*.ipk'):
                if ipk.name.split('_')[0] in names:
                    shutil.copy(ipk, a.out)
        print(len(list(a.out.glob('*.ipk'))), 'packages in', a.out)
        return 0
    if a.cmd == 'pin':
        PINS.write_text(pin(a.feed))
        print(len(PINS.read_text().splitlines()), 'pins written to', PINS)
        return 0
    if a.cmd == 'kmods':
        print(unpack_kmods(a.dir, a.out), 'modules in', a.out)
        return 0
    bad = check_pins(a.dir) if a.cmd == 'fetch' else compare(read_index(a.index), a.dir)
    print('\n'.join(bad) if bad else 'ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
