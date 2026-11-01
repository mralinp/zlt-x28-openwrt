#!/usr/bin/env python3
"""Build an opkg feed that tells the truth about the X28's 4.19 kernel (#200).

The official core feed's kmods need kernel 5.15, and nothing is installed that satisfies them. This feed has a `kernel`
package for the running kernel and an empty package for each feed kmod the kernel already has. Their epoch makes them
outrank the 5.15 packages, so a kmod the kernel lacks fails to install instead of pulling in something unloadable.

  kmod_stub_feed.py map --modules FILE --builtin FILE [--check] [--out package/x28-kmod-stubs/stubs.txt]
  kmod_stub_feed.py build --out DIR [--stubs package/x28-kmod-stubs/stubs.txt]

--modules: one name per line, `ls /lib/modules/4.19.205/*.ko` on the unit, without the suffix.
--builtin: `modules.builtin` from a kernel tree configured with docs/firmware/kernel-4.19.205-x28.config.
Signing is separate: `usign -S -m DIR/Packages -s KEY -x DIR/Packages.sig`.
"""
import argparse
import concurrent.futures
import gzip
import hashlib
import io
import pathlib
import sys
import tarfile
import urllib.request

FEED = 'https://downloads.openwrt.org/releases/23.05.5/targets/armsr/armv8/packages/'
KERNEL = '4.19.205-x28'
VERSION = '1:' + KERNEL
STUBS = pathlib.Path(__file__).resolve().parents[2] / 'package/x28-kmod-stubs/stubs.txt'

# Same code under another name in 4.19.
RENAMED = {'nf_log_syslog': ('nf_log_common', 'nf_log_ipv4', 'nf_log_ipv6'),
           'xt_MASQUERADE': ('ipt_MASQUERADE', 'ip6t_MASQUERADE')}


def norm(name):
    return name.replace('-', '_')


def missing(ko, have):
    def present(m):
        return all(norm(x) in have for x in RENAMED.get(m, (m,)))
    return {m for m in ko if not present(m)}


def covered(kmods, have):
    """Names of the kmods whose modules, and those of their kmod dependencies, are all available."""
    memo = {}

    def ok(name, seen=()):
        if name in seen:
            return True
        if name not in memo:
            k = kmods.get(name)
            memo[name] = bool(k) and not missing(k['ko'], have) and \
                all(ok(d, seen + (name,)) for d in k['depends'] if d.startswith('kmod-'))
        return memo[name]
    return sorted(n for n in kmods if ok(n))


def parse_index(text):
    out, cur = {}, {}
    for line in text.splitlines():
        if not line:
            if cur.get('Package'):
                out[cur['Package']] = cur
            cur = {}
        elif ': ' in line and not line.startswith(' '):
            key, value = line.split(': ', 1)
            cur[key] = value
    return out


def feed_kmods():
    """The feed's index has no file lists, so read them from the packages. Only tar listings; nothing is run."""
    def get(path):
        return urllib.request.urlopen(FEED + path, timeout=120).read()

    def entry(pkg):
        outer = tarfile.open(fileobj=io.BytesIO(get(pkg['Filename'])), mode='r:gz')
        inner = tarfile.open(fileobj=io.BytesIO(outer.extractfile('./data.tar.gz').read()), mode='r:gz')
        return {'ko': {pathlib.PurePath(m.name).stem for m in inner if m.isfile() and m.name.endswith('.ko')},
                'depends': [d.strip().split(' ')[0] for d in pkg.get('Depends', '').split(',') if d.strip()]}
    index = parse_index(gzip.decompress(get('Packages.gz')).decode() + '\n')
    pkgs = {n: p for n, p in index.items() if n.startswith('kmod-')}
    with concurrent.futures.ThreadPoolExecutor(12) as pool:
        return dict(zip(pkgs, pool.map(entry, pkgs.values())))


def tar_gz(files):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', mtime=0) as gz, tarfile.open(fileobj=gz, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        for name, data in files:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def stub(name, depends, description):
    control = ''.join(f'{k}: {v}\n' for k, v in (
        ('Package', name), ('Version', VERSION), ('Depends', depends), ('Section', 'kernel'), ('Architecture', 'all'),
        ('Installed-Size', '0'), ('Description', description)) if v)
    ipk = tar_gz([('./debian-binary', b'2.0\n'), ('./data.tar.gz', tar_gz([])),
                  ('./control.tar.gz', tar_gz([('./control', control.encode())]))])
    return control, ipk


def build(names, out):
    out.mkdir(parents=True, exist_ok=True)
    index = []
    pkgs = [('kernel', '', f'Marks the vendor {KERNEL} kernel as installed.')]
    pkgs += [(n, f'kernel (= {VERSION})', 'Provided by the vendor kernel; installs no files.') for n in names]
    for name, depends, description in pkgs:
        control, ipk = stub(name, depends, description)
        filename = f'{name}_{KERNEL}_all.ipk'
        (out / filename).write_bytes(ipk)
        head = control[:control.index('Description: ')]
        index.append(f'{head}Filename: {filename}\nSize: {len(ipk)}\nSHA256sum: {hashlib.sha256(ipk).hexdigest()}\n'
                     f'Description: {description}\n\n')
    text = ''.join(index).encode()
    (out / 'Packages').write_bytes(text)
    with gzip.GzipFile(out / 'Packages.gz', 'wb', mtime=0) as gz:
        gz.write(text)
    return len(pkgs)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('map')
    m.add_argument('--modules', required=True, type=pathlib.Path)
    m.add_argument('--builtin', required=True, type=pathlib.Path)
    m.add_argument('--out', default=STUBS, type=pathlib.Path)
    m.add_argument('--check', action='store_true', help='fail if the committed list differs')
    b = sub.add_parser('build')
    b.add_argument('--out', required=True, type=pathlib.Path)
    b.add_argument('--stubs', default=STUBS, type=pathlib.Path)
    a = ap.parse_args()
    if a.cmd == 'build':
        print(build(a.stubs.read_text().split(), a.out), 'packages in', a.out)
        return 0
    have = {norm(pathlib.PurePath(x).stem) for f in (a.modules, a.builtin) for x in f.read_text().split()}
    text = '\n'.join(covered(feed_kmods(), have)) + '\n'
    if a.check:
        same = a.out.read_text() == text
        print('stub list matches' if same else 'stub list differs: rerun without --check')
        return 0 if same else 1
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text)
    print(text.count('\n'), 'stubs written to', a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
