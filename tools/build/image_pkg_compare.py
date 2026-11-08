#!/usr/bin/env python3
"""Compare the files of the x28-* packages (package/x28-packages.ini) with an image's rootfs (#417).

  image_pkg_compare.py ROOTFS.tar.gz     (rootfs-management.tar.gz from the flasher)

For every file of every package: is it in the image, with the same content and the same mode? Exit 1 if any differs.
A file that an older image lacks is reported as missing, not as a difference.
"""
import hashlib
import pathlib
import sys
import tarfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import kmod_stub_feed as ks  # noqa: E402


def compare(rootfs, packages):
    tar = tarfile.open(rootfs)
    members = {m.name.lstrip('./'): m for m in tar if m.isfile()}
    rows = []
    for name, _, _, files, _, _, _ in packages:
        for dest, data, mode in files:
            m = members.get(dest.lstrip('./'))
            if m is None:
                status = 'missing'
            else:
                same_content = hashlib.sha256(tar.extractfile(m).read()).digest() == hashlib.sha256(data).digest()
                status = 'same' if same_content and (m.mode & 0o777) == mode else 'differs' + ('' if same_content else ' (content)') + ('' if (m.mode & 0o777) == mode else f' (mode {m.mode & 0o777:o} vs {mode:o})')
            rows.append((name, dest[1:], status))
    return rows


def main():
    rows = compare(sys.argv[1], ks.read_packages())
    for name, dest, status in rows:
        if status != 'same':
            print(f'{status:30} {name}: {dest}')
    counts = {s.split(' ')[0]: sum(1 for r in rows if r[2].split(' ')[0] == s.split(' ')[0]) for s in {r[2] for r in rows}}
    print(f'{len(rows)} files: ' + ', '.join(f'{v} {k}' for k, v in sorted(counts.items())))
    return 1 if any(r[2].startswith('differs') for r in rows) else 0


if __name__ == '__main__':
    sys.exit(main())
