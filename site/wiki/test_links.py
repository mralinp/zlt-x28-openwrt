#!/usr/bin/env python3
"""Checks the wiki: every Page.md link and #anchor resolves, every page is in the sidebar, and every link into this
repository names a file that exists. Run from anywhere: python3 site/wiki/test_links.py"""
import re, sys
from pathlib import Path

W = Path(__file__).resolve().parent
ROOT = W.parent.parent
slug = lambda h: re.sub(r'[^\w\- ]', '', h.lower()).replace(' ', '-')   # GitHub's heading ids, as index.html makes them
text = {f.name: f.read_text(encoding='utf-8') for f in W.glob('*.md')}
ids = {n: {slug(h) for h in re.findall(r'^#+ (.+)$', t, re.M)} | set(re.findall(r'id="([^"]+)"', t)) for n, t in text.items()}
bad = []
for name, t in text.items():
    for href in re.findall(r'\]\(([^)\s]+)\)', t):
        m = re.match(r'https://github\.com/mralinp/zlt-x28-openwrt/(?:blob|tree)/main/([^#]+)', href)
        if m:
            if not (ROOT / m.group(1)).exists():
                bad.append(f'{name}: {href}')
        elif not href.startswith('http'):
            page, _, anchor = href.partition('#')
            if page not in ids or (anchor and anchor not in ids[page]):
                bad.append(f'{name}: {href}')
bad += [f'_Sidebar.md: {n} is not listed' for n in text if n != '_Sidebar.md' and f'({n})' not in text['_Sidebar.md']]
print('\n'.join(bad) or f'wiki ok: {len(text)} files')
sys.exit(bool(bad))
