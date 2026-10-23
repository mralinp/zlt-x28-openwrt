#!/usr/bin/env python3
"""Static safety checks; optional authenticated rendering test with --live."""
import argparse
from html.parser import HTMLParser
from pathlib import Path
import http.cookiejar
import urllib.request
import urllib.parse
import urllib.error

ROOT = Path(__file__).resolve().parent
class PreviewCheck(HTMLParser):
    def __init__(self):
        super().__init__(); self.disabled = []; self.ids = set(); self.inputs = 0; self.buttons = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            assert a['id'] not in self.ids, a['id']
            self.ids.add(a['id'])
        assert tag not in ('form', 'script', 'iframe'), tag
        assert not any(k.startswith('on') for k in a), a
        if tag == 'fieldset': self.disabled.append('disabled' in a)
        if tag == 'input':
            self.inputs += 1
            assert self.disabled and all(self.disabled), a
            assert 'name' not in a, a
        if tag == 'button':
            self.buttons += 1
            assert 'disabled' in a and a.get('type') == 'button', a
    def handle_endtag(self, tag):
        if tag == 'fieldset': self.disabled.pop()

def check(html):
    p=PreviewCheck(); p.feed(html)
    assert p.inputs >= 35 and p.buttons == 2
    assert set(('interfaces','lan','cellular','wireless','firewall','routing','vpn','system')) <= p.ids
    assert not p.disabled

controller=(ROOT/'files/usr/lib/lua/luci/controller/x28_preview.lua').read_text()
template=(ROOT/'files/usr/lib/lua/luci/view/x28/native_preview.htm').read_text()
assert 'REQUEST_METHOD' in controller and '405' in controller and '"GET"' in controller
assert all(s not in controller for s in ('os.execute','io.popen','luci.sys','luci.model.uci','ubus','mipc_wan_cli','fs.writefile'))
check(template)
print('PASS: all eight sections, disabled fields/buttons, GET guard, no write or command execution calls')
parser=argparse.ArgumentParser(); parser.add_argument('--live',action='store_true'); args=parser.parse_args()
if args.live:
    jar=http.cookiejar.CookieJar(); client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    base='http://192.168.70.1:4153/cgi-bin/luci'
    import getpass
    password=getpass.getpass('Current LuCI password: ')
    client.open(base,urllib.parse.urlencode({'luci_username':'root','luci_password':password}).encode(),timeout=15).read()
    page=client.open(base+'/admin/status/x28_native',timeout=15).read().decode()
    # The shared LuCI header contains scripts; inspect only this preview body.
    body=page.split('<!-- x28-preview-start -->',1)[1].split('<!-- x28-preview-end -->',1)[0]
    check(body)
    assert 'ccmni' in body and 'br0' in body
    assert 'stack traceback' not in page and '500 Internal Server Error' not in page
    try:
        client.open(base+'/admin/status/x28_native',b'',timeout=15)
        raise AssertionError('POST was accepted')
    except urllib.error.HTTPError as error: assert error.code == 405
    print('PASS: authenticated live rendering, live devices, disabled controls, POST rejected')
