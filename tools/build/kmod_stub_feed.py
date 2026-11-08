#!/usr/bin/env python3
"""Build an opkg feed that tells the truth about the X28's 4.19 kernel (#200).

The official core feed's kmods need kernel 5.15, and nothing is installed that satisfies them. This feed has a `kernel`
package for the running kernel and an empty package for each feed kmod the kernel already has. Their epoch makes them
outrank the 5.15 packages, so a kmod the kernel lacks fails to install instead of pulling in something unloadable.

  kmod_stub_feed.py map --modules FILE --builtin FILE [--check] [--out package/x28-kmod-stubs/stubs.txt]
  kmod_stub_feed.py build --out DIR [--stubs package/x28-kmod-stubs/stubs.txt] [--kmods DIR]   (--kmods: built .ko files for real.txt)
  kmod_stub_feed.py verify --modules FILE --config FILE --sysmodule FILE --kernel-tree DIR [--stubs FILE]

--modules: one name per line, `ls /lib/modules/4.19.205/*.ko` on the unit, without the suffix.
--builtin: `modules.builtin` from a kernel tree configured with docs/firmware/kernel-4.19.205-x28.config.
verify proves each stub module that has no .ko on the unit is really built in: --config is the unit's `zcat /proc/config.gz`,
--sysmodule its `ls /sys/module`, and --kernel-tree a 4.19 tree used only to map module names to CONFIG options.
Signing is separate: `usign -S -m DIR/Packages -s KEY -x DIR/Packages.sig`.
"""
import argparse
import concurrent.futures
import gzip
import hashlib
import io
import os
import pathlib
import re
import sys
import time
import tarfile
import urllib.request

FEED = 'https://downloads.openwrt.org/releases/23.05.5/targets/armsr/armv8/packages/'
KERNEL = '4.19.205-x28'
VERSION = '1:' + KERNEL
# Bump when the content of any package built from real.txt changes: opkg only upgrades to a higher version.
REV = 2
STUBS = pathlib.Path(__file__).resolve().parents[2] / 'package/x28-kmod-stubs/stubs.txt'
REAL = STUBS.with_name('real.txt')
LOADER = pathlib.Path(__file__).resolve().parents[2] / 'package/x28-kmods/files/x28-kmods.init'
LIST_DIR = './etc/x28-kmods.d'
# An image build enables the loader itself (IPKG_INSTROOT is set then); on a running system opkg does it.
LOADER_SCRIPTS = [('postinst', b'#!/bin/sh\n[ -n "${IPKG_INSTROOT}" ] || /etc/init.d/x28-kmods enable\nexit 0\n'),
                  ('prerm', b'#!/bin/sh\n[ -n "${IPKG_INSTROOT}" ] || /etc/init.d/x28-kmods disable\nexit 0\n')]

# Same code under another name in 4.19.
RENAMED = {'nf_log_syslog': ('nf_log_common', 'nf_log_ipv4', 'nf_log_ipv6'),
           'xt_MASQUERADE': ('ipt_MASQUERADE', 'ip6t_MASQUERADE')}


# OpenWrt pulls this dependency in for packaging reasons; the code the kmod needs is built in without it (kmod-mppe -> arc4, #228).
EXTRA_DEPENDS = {'kmod-crypto-arc4': {'kmod-crypto-user'}}


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
                all(ok(d, seen + (name,)) for d in k['depends']
                    if d.startswith('kmod-') and d not in EXTRA_DEPENDS.get(name, ()))
        return memo[name]
    return sorted(n for n in kmods if ok(n))


def builtin_objects(tree):
    """Module name -> the CONFIG options that build it, from the tree's Makefiles."""
    out = {}
    for root, _, files in os.walk(tree):
        for name in {'Makefile', 'Kbuild'} & set(files):
            text = (pathlib.Path(root) / name).read_text(errors='replace').replace('\\\n', ' ')
            for option, objs in re.findall(r'^\s*obj-\$\((CONFIG_\w+)\)\s*[+:]?=\s*(.*)$', text, re.M):
                for obj in objs.split():
                    if obj.endswith('.o'):
                        out.setdefault(norm(obj[:-2]), set()).add(option)
    return out


def unproven(stubs, kmods, on_unit, objects, config, sysmodules):
    """Stub modules with no .ko on the unit, no =y option in its config and no /sys/module entry."""
    assumed = {norm(m) for name in stubs for m in missing(kmods[name]['ko'], on_unit)}
    return sorted(m for m in assumed if m not in sysmodules and
                  not any(config.get(c) == 'y' for c in objects.get(m, ())))


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


def fetch(url, tries=5):
    """The mirror drops connections now and then; a plain retry is enough."""
    for i in range(tries):
        try:
            return urllib.request.urlopen(url, timeout=120).read()
        except OSError:
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def feed_kmods():
    """The feed's index has no file lists, so read them from the packages. Only tar listings; nothing is run."""
    def get(path):
        return fetch(FEED + path)

    def entry(pkg):
        outer = tarfile.open(fileobj=io.BytesIO(get(pkg['Filename'])), mode='r:gz')
        inner = tarfile.open(fileobj=io.BytesIO(outer.extractfile('./data.tar.gz').read()), mode='r:gz')
        return {'ko': {pathlib.PurePath(m.name).stem for m in inner if m.isfile() and m.name.endswith('.ko')},
                'depends': [d.strip().split(' ')[0] for d in pkg.get('Depends', '').split(',') if d.strip()]}
    index = parse_index(gzip.decompress(get('Packages.gz')).decode() + '\n')
    pkgs = {n: p for n, p in index.items() if n.startswith('kmod-')}
    with concurrent.futures.ThreadPoolExecutor(12) as pool:
        return dict(zip(pkgs, pool.map(entry, pkgs.values())))


def tar_gz(files, dirs=False):
    """dirs: add an entry for every parent directory of the files. opkg does not create missing parent directories (it
    prints `wfopen: ... No such file or directory`, still exits 0 and records the file as installed), so a data archive needs them."""
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', mtime=0) as gz, tarfile.open(fileobj=gz, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        if dirs:
            parents = {'./' + '/'.join(parts[:i]) for name, *_ in files for parts in [name[2:].split('/')[:-1]] for i in range(1, len(parts) + 1)}
            for d in sorted(parents, key=lambda x: (x.count('/'), x)):
                info = tarfile.TarInfo(d)
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                tar.addfile(info)
        for name, data, *mode in files:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            if mode:
                info.mode = mode[0]
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def stub(name, depends, description, files=(), arch='all', scripts=(), version=VERSION):
    control = ''.join(f'{k}: {v}\n' for k, v in (
        ('Package', name), ('Version', version), ('Depends', depends), ('Section', 'kernel'), ('Architecture', arch),
        ('Installed-Size', str(sum(len(f[1]) for f in files))), ('Description', description)) if v)
    ipk = tar_gz([('./debian-binary', b'2.0\n'), ('./data.tar.gz', tar_gz(list(files), dirs=True)),
                  ('./control.tar.gz', tar_gz([('./control', control.encode())] + [('./' + n, d, 0o755) for n, d in scripts]))])
    return control, ipk


def read_real(manifest, kmods):
    """real.txt lines are `package module... [| dependency...]`; the modules are read from the kmods directory."""
    out = []
    for line in manifest.read_text().splitlines():
        names, _, deps = line.partition('|')
        w = names.split()
        if w and w[0][0] != '#':
            out.append((w[0], w[1:], kmods, deps.split()))
    return out


def build(names, out, real=(), loader=None):
    out.mkdir(parents=True, exist_ok=True)
    index = []
    pkgs = [('kernel', '', f'Marks the vendor {KERNEL} kernel as installed.')]
    pkgs += [(n, f'kernel (= {VERSION})', 'Provided by the vendor kernel; installs no files.') for n in names]
    real = list(real)
    deps_of = {n: d for n, m, kmods, d in real}

    def depth(n, seen=()):  # a package loads after the packages of ours that it depends on
        return 1 + max((depth(x, seen + (n,)) for x in deps_of[n] if x in deps_of and x not in seen), default=-1)

    def files_of(n, m, kmods):
        files = [(f'./lib/modules/x28/{x}.ko', (kmods / f'{x}.ko').read_bytes()) for x in m]
        if m:  # the loader (x28-kmods) reads these, in file name order; see package/x28-kmods/files/x28-kmods.init
            files.append((f'{LIST_DIR}/{50 + depth(n):02d}-{n}', ''.join(x + '\n' for x in m).encode()))
        return files
    pkgs += [(n, ', '.join([f'kernel (= {VERSION})'] + d), (f'Modules the vendor kernel lacks, built for it: {" ".join(m)}.' if m else 'Provided by the vendor kernel; installs no files.'),
              files_of(n, m, kmods), 'aarch64_generic') for n, m, kmods, d in real]
    if loader:
        pkgs.append(('x28-kmods', f'kernel (= {VERSION})', 'Loads the modules in /lib/modules/x28 at boot, after the A/B boot counter is reset.',
                     [('./etc/init.d/x28-kmods', pathlib.Path(loader).read_bytes(), 0o755)], 'all', LOADER_SCRIPTS))
    for name, depends, description, *rest in pkgs:
        version = VERSION if not rest else f'{VERSION}-r{REV}'
        control, ipk = stub(name, depends, description, *rest, version=version)
        filename = f'{name}_{version.split(":")[1]}_{"all" if not rest else rest[1]}.ipk'
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
    b.add_argument('--real', default=REAL, type=pathlib.Path, help='manifest of packages that carry our built modules')
    b.add_argument('--kmods', type=pathlib.Path, help='directory with the built .ko files, needed for --real')
    v = sub.add_parser('verify')
    v.add_argument('--modules', required=True, type=pathlib.Path)
    v.add_argument('--config', required=True, type=pathlib.Path)
    v.add_argument('--sysmodule', required=True, type=pathlib.Path)
    v.add_argument('--kernel-tree', required=True, type=pathlib.Path)
    v.add_argument('--stubs', default=STUBS, type=pathlib.Path)
    a = ap.parse_args()
    if a.cmd == 'verify':
        config = dict(re.findall(r'^(CONFIG_\w+)=(.*)$', a.config.read_text(errors='replace'), re.M))
        on_unit = {norm(pathlib.PurePath(x).stem) for x in a.modules.read_text().split()}
        bad = unproven(a.stubs.read_text().split(), feed_kmods(), on_unit, builtin_objects(a.kernel_tree), config,
                       {norm(x) for x in a.sysmodule.read_text().split()})
        print('every stub module is on the unit or built in' if not bad else 'unproven: ' + ' '.join(bad))
        return 1 if bad else 0
    if a.cmd == 'build':
        print(build(a.stubs.read_text().split(), a.out, read_real(a.real, a.kmods), LOADER if a.kmods else None), 'packages in', a.out)
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
