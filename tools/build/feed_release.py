#!/usr/bin/env python3
"""Sign and stage the reviewed #200 ipset feed locally. Never uploads assets or changes a device."""
import argparse
import hashlib
import gzip
import io
from pathlib import Path
import shutil
import subprocess
import tempfile

# Freeze the exact PR #217 candidate; changing a release requires reviewing these identities.
INPUT_HASHES = {
    'Packages': 'a1efdef175022a9028eefbadaeefb3ae38bbfdb192bce9eb87b42d6e067b3474',
    'kernel_4.19.205-x28_all.ipk': '336b75fff89439c58e40ccf972ffd5b7c0e7a903af6af5d93358d940b0a43cfe',
    'x28-ipset-kernel_4.19.205-x28_all.ipk': 'f42bf63ccca0901e7b30a065ac91e5934aea50beb75bfb48004efe8a9fad8c5e',
    'ipset_7.17-1-x28-1_aarch64_generic.ipk': '7c85703a8d3764f21b4a1c776225f55b54d8c5e32171f3fc6c35ce4e52d5fc8a',
    'libipset13_7.17-1-x28-1_aarch64_generic.ipk': 'f2c8171c861571c3774dc82630cd3002f92f64488cda22102c9d59474f982405',
}


def prepare(source, private_key, public_key, output):
    if output.exists():
        raise FileExistsError(output)
    assets = {}
    for name, expected in INPUT_HASHES.items():
        data = (source / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('unreviewed feed asset: ' + name)
        assets[name] = data
    if gzip.decompress((source/'Packages.gz').read_bytes()) != assets['Packages']:
        raise ValueError('compressed index differs from reviewed index')
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode='wb', mtime=0) as stream:
        stream.write(assets['Packages'])
    assets['Packages.gz'] = compressed.getvalue()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.feed-sign-', dir=output.parent) as temporary:
        stage = Path(temporary)
        for name, data in assets.items():
            (stage / name).write_bytes(data)
        shutil.copyfile(public_key, stage / 'x28-feed.pub')
        subprocess.run(['usign', '-S', '-m', str(stage/'Packages'), '-s', str(private_key),
                        '-x', str(stage/'Packages.sig')], check=True)
        subprocess.run(['usign', '-V', '-m', str(stage/'Packages'), '-p', str(stage/'x28-feed.pub'),
                        '-x', str(stage/'Packages.sig')], check=True)
        sums = ''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n'
                       for p in sorted(stage.iterdir()))
        (stage/'SHA256SUMS').write_text(sums)
        shutil.copytree(stage, output)  # Exclusive destination; never replaces an existing release.
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--feed', type=Path, required=True)
    parser.add_argument('--private-key', type=Path, required=True)
    parser.add_argument('--public-key', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.feed, args.private_key, args.public_key, args.out)
    print('Signature verified; release assets staged locally:', args.out)


if __name__ == '__main__':
    main()
