local M = {}
local util = require "luci.util"
local json = require "luci.jsonc"
local fs = require "nixio.fs"
local function node(title, action, order)
 return {title=title, action=action or {type="firstchild",recurse=true}, order=order or 10,
  satisfied=true, readonly=true, children={}}
end
function M.menu()
 local root=node(nil); local admin=node("Administration")
 root.children.admin=admin; admin.auth={methods={"cookie:sysauth"}, login=true}
 local groups={{"status","Status"},{"system","System"},{"network","Network"}}
 for i,g in ipairs(groups) do admin.children[g[1]]=node(g[2],nil,i*10) end
 local pages={
  {"status","overview","Overview","status/index"},
  {"status","routes","Routes","status/routes"},
  {"status","processes","Processes","status/processes"},
  {"system","system","System","system/system"},
  {"system","startup","Startup","system/startup"},
  {"network","network","Interfaces","network/interfaces"},
  {"network","wireless","Wireless","network/wireless"},
  {"network","dhcp","DHCP and DNS","network/dhcp"},
  {"network","routes","Static Routes","network/routes"},
  {"network","hosts","Hostnames","network/hosts"},
  {"network","firewall","Firewall","firewall/zones"},
  {"network","forwards","Port Forwards","firewall/forwards"},
  {"network","rules","Traffic Rules","firewall/rules"},
  {"network","snats","NAT Rules","firewall/snats"}
 }
 for i,p in ipairs(pages) do
  admin.children[p[1]].children[p[2]]=node(p[3],{type="view",path=p[4]},i)
 end
 admin.children.translations=node(nil,{type="call",module="luci.controller.admin.index",["function"]="action_translations"})
 admin.children.translations.wildcard=true
 admin.children.menu=node(nil,{type="call",module="stock",["function"]="menu_reply"})
 admin.children.ubus=node(nil,{type="call",module="stock",["function"]="rpc"})
 return root
end
function M.menu_reply() luci.http.prepare_content("application/json"); luci.http.write_json(M.menu()) end
local function read(path) return fs.readfile(path) or "" end
local function section(t,n,index,values)
 values=values or {}; values[".type"]=t; values[".name"]=n; values[".index"]=index; values[".anonymous"]=false; return values
end
local function snapshot()
 local devs=util.ubus("luci-rpc","getNetworkDevices",{}) or {}
 local default
 for line in read("/proc/net/route"):gmatch("[^\n]+") do
  local name,dest=line:match("^(%S+)%s+(%x+)")
  if dest=="00000000" then default=name; break end
 end
 local configs={network={},wireless={}}
 local status={}
 local function add(name,device,proto)
  local d=devs[device]; if not d then return end
  local c={proto=proto,ifname=device,auto="0"}
  if proto=="static" and d.ipaddrs and d.ipaddrs[1] then c.ipaddr=d.ipaddrs[1].address; c.netmask=d.ipaddrs[1].netmask end
  configs.network[name]=section("interface",name,#status,c)
  local ip,ip6={},{}
  for _,a in ipairs(d.ipaddrs or {}) do
   local prefix=0
   for octet in (a.netmask or "255.255.255.255"):gmatch("%d+") do
    local n=tonumber(octet); while n>0 do prefix=prefix+n%2; n=math.floor(n/2) end
   end
   ip[#ip+1]={address=a.address,mask=prefix}
  end
  for _,a in ipairs(d.ip6addrs or {}) do ip6[#ip6+1]={address=a.address,mask=tonumber(a.netmask) or 64} end
  status[#status+1]={interface=name,proto=proto,up=d.up or false,pending=false,available=true,
   autostart=false,dynamic=false,device=device,l3_device=device,uptime=0,
   ["ipv4-address"]=ip,["ipv6-address"]=ip6,["ipv6-prefix"]={},["ipv6-prefix-assignment"]={},
   route={},["dns-server"]={},data={preview=true}}
 end
 add("lan","br0","static")
 if default and default~="br0" then add("wan",default,"x28_mipc") end
 -- Profile mapping is observational; no passwords or driver controls are exposed.
 for i,p in ipairs({{"/etc/wireless/mediatek/mt7915.1.dat","ra","radio0"},
                   {"/etc/wireless/mediatek/mt7915.2.dat","rai","radio1"}}) do
  local profile={}
  for key,value in read(p[1]):gmatch("([%w_]+)=([^\r\n]*)") do
   if key=="Channel" or key=="SSID1" then profile[key]=value end
  end
  if profile.SSID1 and devs[p[2].."0"] then
   configs.wireless[p[3]]=section("wifi-device",p[3],i*2,{type="mtwifi",channel=profile.Channel or "auto",disabled=devs[p[2].."0"].up and "0" or "1"})
   configs.wireless["default_"..p[3]]=section("wifi-iface","default_"..p[3],i*2+1,
    {device=p[3],ifname=p[2].."0",network="lan",mode="ap",ssid=profile.SSID1})
  end
 end
 return configs,status
end
local allowed={
 ["luci-rpc"]={getNetworkDevices=true,getBoardJSON=true,getHostHints=true,getDUIDHints=true,getDHCPLeases=true},
 luci={getFeatures=true,getInitList=true,getLocaltime=true,getTimezones=true,getLEDs=true,getMountPoints=true,getProcessList=true},
 system={board=true,info=true},
}
local configs_allowed={dhcp=true,firewall=true,system=true,luci=true}
local function clean(value)
 if type(value)~="table" then return value end
 local result={}
 for k,v in pairs(value) do
  if not tostring(k):lower():match("password") and not tostring(k):lower():match("secret") and
     not tostring(k):lower():match("key") then result[k]=clean(v) end
 end
 return result
end
function M.read_call(object,method,args)
 args=args or {}
 if object=="session" and method=="access" then
  if args.scope then return 0,{access=false} end
  return 0,{["access-group"]={},uci={}}
 end
 if object=="uci" then
  if method=="changes" then return 0,{changes={}} end
  if method~="get" then return 6 end
  if args.config=="network" or args.config=="wireless" then
   local configs=snapshot(); return 0,{values=configs[args.config]}
  end
  if not configs_allowed[args.config] then return 6 end
  local cursor=require("luci.model.uci").cursor()
  local values={}; local index=0
  cursor:foreach(args.config,nil,function(s) s[".index"]=index; index=index+1; values[s[".name"]]=clean(s) end)
  return 0,{values=values}
 end
 if object=="network.interface" and method=="dump" then local _,status=snapshot(); return 0,{interface=status} end
 if object=="network" and method=="get_proto_handlers" then
  return 0,{static={no_device=false},none={no_device=false},dhcp={no_device=false},x28_mipc={no_device=true}}
 end
 if object=="luci-rpc" and method=="getWirelessDevices" then return 0,{} end
 if object=="file" and method=="list" and args.path=="/sys/class/net" then
  local entries={}; for name in fs.dir("/sys/class/net") do entries[#entries+1]={name=name,type="directory"} end
  return 0,{entries=entries}
 end
 if allowed[object] and allowed[object][method] then
  local value=util.ubus(object,method,{})
  return value and 0 or 4,value
 end
 return 6
end
function M.rpc()
 local http=require "luci.http"
 if http.getenv("REQUEST_METHOD")~="POST" then http.status(405,"Method Not Allowed"); return end
 local body=json.parse(http.content() or "")
 local function one(call)
  if type(call)~="table" then return {jsonrpc="2.0",error={code=-32600,message="Invalid request"}} end
  local result={jsonrpc="2.0",id=call.id}
  if call.method~="call" or type(call.params)~="table" or type(call.params[2])~="string" or type(call.params[3])~="string" or
   (call.params[4]~=nil and type(call.params[4])~="table") then result.result={6}; return result end
  if call.params[1]~=luci.dispatcher.context.authsession then result.result={6}; return result end
  local code,data=M.read_call(call.params[2],call.params[3],call.params[4])
  result.result={code}; if data then result.result[2]=data end
  return result
 end
 local reply
 if type(body)=="table" and body[1] then
  reply={}; for i,call in ipairs(body) do if i>64 then break end; reply[i]=one(call) end
 else reply=one(body) end
 http.prepare_content("application/json"); http.write_json(reply)
end
return M
