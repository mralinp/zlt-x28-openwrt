#!/usr/bin/env python3
"""Sign and stage the reviewed #200 feed locally. Never uploads assets or changes a device."""
import argparse
import hashlib
import gzip
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
from kmod_stub_feed import parse_index

# The index holds every package's SHA-256, so this pin freezes the whole feed. Changing a release means reviewing it again.
INDEX_SHA256 = '54d545546b82ac1fa1f073336a947a05283df4df6c3e46a49bf19fbff42d51a1'  # the X28 feed, 213 packages: docs/research/feed-index.txt


def prepare(source, private_key, public_key, output):
    if output.exists():
        raise FileExistsError(output)
    index = (source/'Packages').read_bytes()
    if hashlib.sha256(index).hexdigest() != INDEX_SHA256:
        raise ValueError('unreviewed feed index')
    if gzip.decompress((source/'Packages.gz').read_bytes()) != index:
        raise ValueError('compressed index differs from reviewed index')
    assets = {'Packages': index}
    for package in parse_index(index.decode() + '\n').values():
        name = package['Filename']
        if Path(name).name != name:
            raise ValueError('package outside the feed: ' + name)
        data = (source/name).read_bytes()
        if hashlib.sha256(data).hexdigest() != package['SHA256sum']:
            raise ValueError('package differs from reviewed index: ' + name)
        assets[name] = data
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode='wb', mtime=0) as stream:
        stream.write(index)
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
