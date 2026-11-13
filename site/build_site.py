#!/usr/bin/env python3
"""Builds the landing page data: site/ + the newest feed-N release + stats.json -> _site/.
Needs the gh CLI (GH_TOKEN in CI). Usage: build_site.py [outdir]"""
import datetime, json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / '_site')
FW, FL = 'mralinp/zlt-x28-openwrt', 'mralinp/x28-flasher'


def gh(*a):
    return subprocess.run(['gh', *a], check=True, capture_output=True, text=True).stdout


def downloads(repo):
    return sum(a['download_count'] for pages in json.loads(gh('api', '--paginate', '--slurp', f'repos/{repo}/releases?per_page=100')) for r in pages for a in r['assets'])


def release(repo):
    try:
        r = json.loads(gh('api', f'repos/{repo}/releases/latest'))
    except subprocess.CalledProcessError:  # only pre-releases so far (the flasher's 0.x): take the newest
        r = json.loads(gh('api', f'repos/{repo}/releases?per_page=1'))[0]
    return {'tag': r['tag_name'], 'url': r['html_url'], 'date': r['published_at'][:10],
            'assets': [{'name': a['name'], 'size': a['size'], 'downloads': a['download_count'], 'url': a['browser_download_url']} for a in r['assets']]}


def tests():
    rows = []
    for line in (ROOT / 'docs/TESTING.md').read_text(encoding='utf-8').split('## Summary')[1].splitlines():
        c = [x.strip() for x in line.strip().strip('|').split('|')]
        if len(c) >= 5 and c[0].isdigit():
            rows.append({'n': c[0], 'name': c[1], 'date': c[2], 'result': c[3]})
    ok = sum(r['result'].startswith('✅') for r in rows)
    bad = sum(r['result'].startswith('❌') for r in rows)
    return {'total': len(rows), 'passed': ok, 'failed': bad, 'other': len(rows) - ok - bad, 'recent': rows[-8:][::-1]}


def feed():
    """Mirrors the newest feed-N release into _site/feed (a signed opkg feed: opkg checks the signature, not the host)."""
    tags = sorted((t for t in gh('release', 'list', '-R', FW, '--limit', '100', '--json', 'tagName', '-q', '.[].tagName').split() if re.fullmatch(r'feed-\d+', t)),
                  key=lambda t: int(t[5:]))
    if not tags:
        raise SystemExit('no feed-N release')
    dest = OUT / 'feed'
    dest.mkdir(parents=True)
    gh('release', 'download', tags[-1], '-R', FW, '-D', str(dest), '--clobber')
    for need in ('Packages', 'Packages.gz', 'Packages.sig'):
        if not (dest / need).is_file():
            raise SystemExit(f'{tags[-1]} has no {need}')
    return {'tag': tags[-1], 'packages': len(re.findall(r'^Package: ', (dest / 'Packages').read_text(), re.M))}


if OUT.exists():
    shutil.rmtree(OUT)
shutil.copytree(ROOT / 'site', OUT, ignore=shutil.ignore_patterns('build_site.py', 'test_*'))
(OUT / '.nojekyll').write_text('')
stats = {'stars': {r: json.loads(gh('api', f'repos/{r}'))['stargazers_count'] for r in (FW, FL)},
         'downloads': {FW: downloads(FW), FL: downloads(FL)},
         'firmware': release(FW), 'flasher': release(FL), 'feed': feed(), 'tests': tests(),
         'built': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
(OUT / 'stats.json').write_text(json.dumps(stats, indent=1))
print(f"site ok: {stats['stars']} stars, {sum(stats['downloads'].values())} downloads, feed {stats['feed']}, {stats['tests']['passed']}/{stats['tests']['total']} tests")
