#!/usr/bin/env python3
"""Classify every kmod of the official 23.05.5 core feed for the X28's 4.19.205 kernel (#394). Read-only.

  A  stub: every module is on the unit or built in (package/x28-kmod-stubs/stubs.txt)
  B  buildable: every missing module has 4.19 source and setting just its CONFIG option =m changes no other built-in symbol
  C  blocked: source exists but the option stays off, or enabling it also changes built-in symbols (needs a kernel config change)
  D  no 4.19 source: the module is newer than the kernel or out of tree (needs a backport)
A kmod takes the worst class of its own modules and of the kmods it depends on.

  kmod_gap.py --modules FILE --tree DIR [--config FILE] [--out FILE.md]
  kmod_gap.py --selftest

--modules: `ls /lib/modules/4.19.205/*.ko` from the unit (one path per line). --tree: the configured SDK tree (private).
The tree is only read: olddefconfig writes to a temp file via KCONFIG_CONFIG. Needs make and the tree's built scripts/kconfig/conf.
Userspace dependents come from the official base, packages and luci indexes (direct `Depends` only, not through libraries).
"""
import argparse
import collections
import concurrent.futures
import gzip
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import kmod_stub_feed as ks  # noqa: E402

REPO = 'https://downloads.openwrt.org/releases/23.05.5/packages/aarch64_generic/'
STUBS = ks.STUBS
CLASSES = 'ABCD'


def resolve(tree, config, options):
    """option -> 'm' if setting just that option =m via olddefconfig changes nothing else but other new =m modules,
    else why not ('off' or the other symbols it drags in)."""
    def run(extra):
        with tempfile.NamedTemporaryFile('w', suffix='.config') as f:
            text = pathlib.Path(config).read_text()
            for o in extra:
                text = re.sub(rf'^(# {o} is not set|{o}=.*)\n', '', text, flags=re.M)
            f.write(text + ''.join(f'{o}=m\n' for o in extra))
            f.flush()
            subprocess.run(['make', '-C', str(tree), 'ARCH=arm64', f'KCONFIG_CONFIG={f.name}', 'olddefconfig'],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return dict(re.findall(r'^(CONFIG_\w+)=(.*)$', pathlib.Path(f.name).read_text(), re.M))
    base = run(())

    def one(o):
        got = run((o,))
        if got.get(o) != 'm':
            return o, 'off'
        more = sorted(f'{s}={v}' for s, v in got.items() if s != o and v != 'm' and base.get(s) != v)
        return o, 'm' if not more else 'also sets ' + ' '.join(more[:3])
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        return dict(pool.map(one, sorted(options)))


def classify(kmods, have, stubs, objects, final):
    """kmod -> (class, [reasons]); objects: module -> options, final: option -> value after olddefconfig."""
    own = {}
    for name, k in kmods.items():
        if name in stubs:
            own[name] = ('A', [])
            continue
        why, worst = [], 'B'
        for m in sorted(ks.missing(k['ko'], have)):
            opts = objects.get(ks.norm(m), ())
            if not opts:
                why.append(f'{m}: no 4.19 source')
                worst = 'D'
            elif not any(final.get(o) == 'm' for o in opts):
                why.append(f'{m}: ' + '; '.join(f'{o} {final.get(o, "off")}' for o in sorted(opts)))
                worst = max(worst, 'C')
        own[name] = (worst, why)
    memo = {}

    def total(name, seen=()):
        if name in memo or name in seen:
            return memo.get(name, ('A', []))
        cls, why = own[name]
        why = list(why)
        for d in kmods[name]['depends']:
            if d.startswith('kmod-') and d in kmods and d not in ks.EXTRA_DEPENDS.get(name, ()):
                dc, _ = total(d, seen + (name,))
                if dc > cls:
                    cls = dc
                if dc > 'B':
                    why.append(f'needs {d} ({dc})')
        memo[name] = (cls, why)
        return memo[name]
    return {n: total(n) for n in kmods}


def dependents(kmods):
    """kmod -> sorted user packages (from base, packages, luci) that depend on it directly."""
    out = collections.defaultdict(set)
    for repo in ('base', 'packages', 'luci'):
        data = urllib.request.urlopen(f'{REPO}{repo}/Packages.gz', timeout=120).read()
        for name, p in ks.parse_index(gzip.decompress(data).decode() + '\n').items():
            for d in p.get('Depends', '').split(','):
                d = d.strip().split(' ')[0]
                if d in kmods and not name.startswith('kmod-'):
                    out[d].add(name)
    return out


def report(result, deps_of):
    n = collections.Counter(c for c, _ in result.values())
    lines = [f'{len(result)} kmods: ' + ', '.join(f'{c} {n[c]}' for c in CLASSES), '',
             '| Kmod | Class | Why | User packages that depend on it |', '|---|---|---|---|']
    for name in sorted(result, key=lambda x: (result[x][0], -len(deps_of.get(x, ())), x)):
        cls, why = result[name]
        if cls != 'A':
            users = sorted(deps_of.get(name, ()))
            shown = ', '.join(users[:6]) + (f' (+{len(users) - 6})' if len(users) > 6 else '')
            lines.append(f'| `{name}` | {cls} | {"; ".join(why) or "buildable"} | {shown} |')
    users = {u for k, (c, _) in result.items() if c > 'B' for u in deps_of.get(k, ())}
    lines.append(f'user packages with a direct dependency on a C or D kmod: {len(users)}')
    luci = sorted({u for k, (c, _) in result.items() if c > 'B' for u in deps_of.get(k, ()) if u.startswith('luci-')})
    lines += ['', f'luci packages with a direct dependency on a C or D kmod: {len(luci)}', ', '.join(luci)]
    return '\n'.join(lines) + '\n'


def selftest():
    kmods = {'kmod-a': {'ko': {'a'}, 'depends': []}, 'kmod-b': {'ko': {'b'}, 'depends': ['kmod-a']},
             'kmod-c': {'ko': {'c'}, 'depends': []}, 'kmod-d': {'ko': {'d'}, 'depends': []},
             'kmod-e': {'ko': {'e'}, 'depends': ['kmod-d']}, 'kmod-s': {'ko': {'s'}, 'depends': []}}
    r = classify(kmods, set(), {'kmod-s'}, {'a': {'CONFIG_A'}, 'b': {'CONFIG_B'}, 'c': {'CONFIG_C'}},
                 {'CONFIG_A': 'm', 'CONFIG_B': 'm', 'CONFIG_C': 'n'})
    got = {k: v[0] for k, v in r.items()}
    assert got == {'kmod-a': 'B', 'kmod-b': 'B', 'kmod-c': 'C', 'kmod-d': 'D', 'kmod-e': 'D', 'kmod-s': 'A'}, got
    print('selftest ok')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--modules', type=pathlib.Path)
    ap.add_argument('--tree', type=pathlib.Path)
    ap.add_argument('--config', type=pathlib.Path)
    ap.add_argument('--out', type=pathlib.Path)
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    kmods = ks.feed_kmods()
    on_unit = {ks.norm(pathlib.PurePath(x).stem) for x in a.modules.read_text().split()}
    builtin = {ks.norm(pathlib.PurePath(x).stem) for x in (a.tree / 'modules.builtin').read_text().split()}
    have = on_unit | builtin
    objects = ks.builtin_objects(a.tree)
    stubs = set(STUBS.read_text().split())
    want = {o for k, v in kmods.items() if k not in stubs for m in ks.missing(v['ko'], have) for o in objects.get(ks.norm(m), ())}
    final = resolve(a.tree, a.config or a.tree / '.config', want)
    result = classify(kmods, have, stubs, objects, final)
    text = report(result, dependents(kmods))
    (a.out.write_text(text) if a.out else print(text, end=''))


if __name__ == '__main__':
    sys.exit(main())
