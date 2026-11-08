#!/usr/bin/env python3
"""Build the local X28 feed: kmod stubs plus ipset for the observed vendor subset (#200); no device operations.

The upstream payload and maintainer scripts are preserved. Only ipset's version,
description and kernel dependency metadata change. This does
not provide the complete official kmod-ipt-ipset aggregate or add kernel features.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import kmod_stub_feed as feed

UPSTREAM_SHA = 'df8a2a483104b8ea5fd544e8feac78b220128ae4703851c8d80d88927ebff5bf'
LIBRARY_SHA = '6965342a8d2170b34992cfea8fc5dde460253b6143d5908af1bbfa456f9a4809'
UPSTREAM_URL = 'https://downloads.openwrt.org/releases/23.05.5/packages/aarch64_generic/base/ipset_7.17-1_aarch64_generic.ipk'
VERSION = '1:7.17-1-x28-1'
REQUIRED_MODULES = frozenset(('ip_set ip_set_bitmap_ip ip_set_bitmap_ipmac ip_set_bitmap_port '
    'ip_set_hash_ip ip_set_hash_ipmark ip_set_hash_ipport ip_set_hash_ipportip ip_set_hash_ipportnet '
    'ip_set_hash_mac ip_set_hash_net ip_set_hash_netiface ip_set_hash_netnet ip_set_hash_netport '
    'ip_set_hash_netportnet ip_set_list_set xt_set nfnetlink x_tables').split())
DESCRIPTION = 'Vendor ipset subset; hash:ip,mac is unavailable. Installs no modules.'


def repackage(upstream, modules, name='ipset'):
    if hashlib.sha256(upstream).hexdigest() != {'ipset': UPSTREAM_SHA, 'libipset13': LIBRARY_SHA}[name]:
        raise ValueError('unknown upstream ipset package')
    missing = REQUIRED_MODULES - set(modules)
    if missing:
        raise ValueError('missing observed vendor modules: ' + ', '.join(sorted(missing)))
    with tarfile.open(fileobj=io.BytesIO(upstream), mode='r:gz') as outer:
        data = outer.extractfile('./data.tar.gz').read()
        original_control = outer.extractfile('./control.tar.gz').read()
    buf = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(original_control), mode='r:gz') as src, \
            gzip.GzipFile(fileobj=buf, mode='wb', mtime=0) as gz, \
            tarfile.open(fileobj=gz, mode='w', format=tarfile.USTAR_FORMAT) as dst:
        for member in src:
            content = src.extractfile(member).read() if member.isfile() else None
            if member.name == './control':
                text = content.decode()
                fields = feed.parse_index(text + '\n')[name]
                expected = 'libc, kmod-ipt-ipset, libmnl0' + (', libipset13' if name == 'ipset' else '')
                if fields['Version'] != '7.17-1' or fields['Architecture'] != 'aarch64_generic' or \
                        fields['Depends'] != expected:
                    raise ValueError('unexpected upstream metadata')
                text = text.replace('Version: 7.17-1\n', 'Version: ' + VERSION + '\n')
                if name == 'ipset':
                    text = text.replace(', libipset13\n', ', libipset13 (= ' + VERSION + ')\n')
                text = text.replace('kmod-ipt-ipset', 'x28-ipset-kernel (= ' + feed.VERSION + ')')
                text = '\n'.join('Description: X28 ipset utility; hash:ip,mac unavailable.' if line.startswith('Description:') else line for line in text.split('\n'))
                text = text.rstrip() + '\nX28-Limit: hash:ip,mac is unavailable; vendor module subset only.\n'
                content = text.encode()
                member.size = len(content)
            dst.addfile(member, io.BytesIO(content) if content is not None else None)
    result = feed.tar_gz([('./debian-binary', b'2.0\n'), ('./data.tar.gz', data), ('./control.tar.gz', buf.getvalue())])
    return text, result


def build(upstream, library, modules, out, stubs=(), real=(), packages=()):
    control, package = repackage(upstream, modules)
    library_control, library_package = repackage(library, modules, 'libipset13')
    out.mkdir(parents=True, exist_ok=False)
    feed.build(list(stubs), out, real, feed.LOADER if real else None, packages)
    marker, marker_ipk = feed.stub('x28-ipset-kernel', 'kernel (= ' + feed.VERSION + ')', DESCRIPTION)
    for filename, metadata, payload in (
            ('x28-ipset-kernel_4.19.205-x28_all.ipk', marker, marker_ipk),
            ('ipset_7.17-1-x28-1_aarch64_generic.ipk', control, package),
            ('libipset13_7.17-1-x28-1_aarch64_generic.ipk', library_control, library_package)):
        (out / filename).write_bytes(payload)
        with (out / 'Packages').open('a') as stream:
            stream.write(metadata.rstrip() + '\nFilename: ' + filename + '\nSize: ' + str(len(payload)) +
                         '\nSHA256sum: ' + hashlib.sha256(payload).hexdigest() + '\n\n')
    (out / 'Packages.gz').write_bytes(gzip.compress((out / 'Packages').read_bytes(), mtime=0))
    manifest = {'upstream_url': UPSTREAM_URL, 'upstream_sha256': UPSTREAM_SHA,
                'library_upstream_sha256': LIBRARY_SHA,
                'ipset_sha256': hashlib.sha256(package).hexdigest(),
                'libipset13_sha256': hashlib.sha256(library_package).hexdigest(), 'required_modules': sorted(REQUIRED_MODULES),
                'limitation': DESCRIPTION, 'runtime_tested': False}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--modules', type=Path, required=True, help='read-only observed module-file inventory')
    parser.add_argument('--out', type=Path, required=True, help='new private output directory')
    parser.add_argument('--stubs', type=Path, default=feed.STUBS, help='kmod stub list to include')
    parser.add_argument('--real', type=Path, default=feed.REAL, help='manifest of packages that carry our built modules')
    parser.add_argument('--x28-packages', action='store_true', help='also build the x28-* packages of package/x28-packages.ini (#417; not for the live feed before #418)')
    parser.add_argument('--nrband', type=Path, help='the x28-nrband binary (tools/build/x28_nrband.sh): adds the x28-nrband package')
    parser.add_argument('--kmods', type=Path, help='directory with the built .ko files; without it only the stubs and ipset are built')
    args = parser.parse_args()
    modules = {Path(name).stem for name in args.modules.read_text().split()}
    build(args.upstream.read_bytes(), args.library.read_bytes(), modules, args.out, args.stubs.read_text().split(),
          feed.read_real(args.real, args.kmods) if args.kmods else (),
          (feed.read_packages() if args.x28_packages else []) + ([feed.nrband_package(args.nrband)] if args.nrband else []))
    print('Local feed built; unsigned and not deployed:', args.out)


if __name__ == '__main__':
    main()
