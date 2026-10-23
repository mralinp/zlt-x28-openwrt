package.path='/tmp/x28-stock-luci/?.lua;'..package.path
local util=require 'luci.util'
local calls=0
util.ubus=function() calls=calls+1; error('unexpected RPC forwarding') end
local stock=require 'stock'
for _,test in ipairs({
 {'uci','set',{config='network'}},{'uci','add',{}},{'uci','delete',{}},{'uci','apply',{}},{'uci','commit',{}},{'uci','revert',{}},
 {'file','exec',{command='/sbin/reboot'}},{'file','read',{path='/etc/shadow'}},{'file','write',{}},
 {'network','reload',{}},{'network.interface.wan','down',{}},{'system','reboot',{}},
 {'iwinfo','scan',{}},{'hostapd.ra0','del_client',{}},{'uci','get',{config='../shadow'}},
 {'session','login',{}},{'session','destroy',{}},{'service','set',{}},
 {'luci','setInitAction',{}},{'luci','setPassword',{}}
}) do assert(stock.read_call(unpack(test))==6, test[1]..'.'..test[2]) end
assert(calls==0)
local m=stock.menu()
assert(m.children.admin.auth.login)
assert(m.children.admin.children.network.children.network.action.path=='network/interfaces')
assert(m.children.admin.children.network.children.wireless.action.path=='network/wireless')
assert(m.children.admin.children.network.children.firewall.action.path=='firewall/zones')
assert(m.children.admin.children.system.children.system.readonly)
assert(not m.children.admin.children.system.children.flash)
print('PASS: 20 mutation/secret access attempts denied without forwarding; genuine stock view routes, auth and readonly flags')
