import getpass
import urllib.request,urllib.parse,http.cookiejar,urllib.error,json
from pathlib import Path
base='http://192.168.70.1:4154/cgi-bin/luci-stock'
c=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
try:
 c.open(base,urllib.parse.urlencode({'luci_username':'root','luci_password':getpass.getpass('Current LuCI password: ')}).encode(),timeout=15).read()
except urllib.error.HTTPError as e:
 print(e.read().decode()[:2000]);raise
for path in ['network/network','network/wireless','network/dhcp','network/firewall','system/system','status/overview']:
 try: s=c.open(base+'/admin/'+path,timeout=15).read().decode()
 except urllib.error.HTTPError as e: print(e.read().decode()[:2000]);raise
 assert '500 Internal' not in s and 'READ-ONLY' in s,(path,s[-1500:])
 assert '"readonly":true' in s,path
 Path('work/x28-stock-preview/last-render.html').write_text(s)
 print('PASS stock page',path)
cookie=next(cookie.value for handler in c.handlers if hasattr(handler,'cookiejar') for cookie in handler.cookiejar if cookie.name=='sysauth')
def call(obj,method,args):
 data=json.dumps({'jsonrpc':'2.0','id':1,'method':'call','params':[cookie,obj,method,args]}).encode()
 return json.load(c.open(urllib.request.Request(base+'/admin/ubus',data,{'Content-Type':'application/json'}),timeout=15))
for obj,method,args in [('uci','set',{'config':'network'}),('uci','apply',{}),('file','exec',{'command':'/sbin/ifdown','params':['wan']}),('system','reboot',{})]:
 assert call(obj,method,args)['result']==[6]
 print('PASS blocked',obj,method)
assert call('network.interface','dump',{})['result'][1]['interface']
assert call('uci','get',{'config':'network'})['result'][1]['values']['lan']['ipaddr']=='192.168.70.1'
print('PASS live LAN mapping and runtime interface dump')
try:
 c.open(base+'/admin/network/network',b'',timeout=15);raise AssertionError('page POST accepted')
except urllib.error.HTTPError as e:assert e.code==405
print('PASS non-RPC page POST blocked')
