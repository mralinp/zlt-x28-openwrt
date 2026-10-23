module("luci.controller.x28_preview", package.seeall)

function index()
 entry({"admin", "status", "x28_native"}, call("preview"), _("Native OpenWrt preview"), 95).leaf = true
end

function preview()
 local http = require "luci.http"
 if http.getenv("REQUEST_METHOD") ~= "GET" then
  http.status(405, "Method Not Allowed")
  http.header("Allow", "GET")
  http.write("Read-only preview")
  return
 end
 local fs = require "nixio.fs"
 local function read(path) return fs.readfile(path) or "" end
 local devices, wireless, bridges = {}, {}, {}
 for name in read("/proc/net/wireless"):gmatch("([%w_.-]+):") do wireless[name] = true end
 for _, address in ipairs(require("nixio").getifaddrs() or {}) do
  if address.family == "packet" and address.name ~= "lo" then
   local members = {}
   if fs.access("/sys/class/net/" .. address.name .. "/bridge") then
    for member in fs.dir("/sys/class/net/" .. address.name .. "/brif") do members[#members + 1] = member end
    table.sort(members)
    bridges[#bridges + 1] = {name = address.name, members = table.concat(members, ", ")}
   end
   devices[#devices + 1] = {name = address.name, up = address.flags and address.flags.up,
    wireless = wireless[address.name], mtu = read("/sys/class/net/" .. address.name .. "/mtu"):match("%d+") or "Unknown"}
  end
 end
 table.sort(devices, function(a, b) return a.name < b.name end)
 table.sort(bridges, function(a, b) return a.name < b.name end)
 local addresses = {}
 for _, address in ipairs(require("nixio").getifaddrs() or {}) do
  if (address.family == "inet" or address.family == "inet6") and address.name ~= "lo" then
   addresses[#addresses + 1] = {name = address.name, address = address.addr, prefix = address.prefix}
  end
 end
 table.sort(addresses, function(a, b) return a.name .. a.address < b.name .. b.address end)
 local dns = {}
 for server in read("/etc/resolv.conf"):gmatch("nameserver%s+([^%s]+)") do dns[#dns + 1] = server end
 local lease_count = 0
 for line in read("/tmp/dnsmasq.leases"):gmatch("[^\n]+") do
  if line:match("^%d+%s+") then lease_count = lease_count + 1 end
 end
 local capabilities = {}
 for _, item in ipairs({
  {"netifd executable", "/sbin/netifd"}, {"dnsmasq executable", "/usr/sbin/dnsmasq"},
  {"odhcpd executable", "/usr/sbin/odhcpd"}, {"OpenWrt firewall (fw3)", "/sbin/fw3"},
  {"OpenVPN executable", "/usr/sbin/openvpn"}, {"WireGuard kernel module loaded", "/sys/module/wireguard"},
  {"TUN device", "/dev/net/tun"}, {"Passwall2 init script", "/etc/init.d/passwall2"},
  {"Native X28 protocol installed", "/lib/netifd/proto/x28_mipc.sh"},
  {"netifd wireless backend directory", "/lib/netifd/wireless"}
 }) do capabilities[#capabilities + 1] = {name = item[1], present = fs.access(item[2]) and true or false} end
 local processes = {}
 local tracked = {netifd=true, lan_mgr=true, wan_mgr=true, mtk_netagent=true, mipc_submonitor=true,
  wapp=true, dnsmasq=true, odhcpd=true, openvpn=true, dropbear=true, uhttpd=true}
 for pid in fs.dir("/proc") do
  if pid:match("^%d+$") then
   local name = read("/proc/" .. pid .. "/comm"):match("([^\n]+)")
   if name and tracked[name] then processes[name] = (processes[name] or 0) + 1 end
  end
 end
 local services = {}
 for name in pairs(tracked) do services[#services + 1] = {name = name, count = processes[name] or 0} end
 table.sort(services, function(a,b) return a.name < b.name end)
 require("luci.template").render("x28/native_preview", {
  devices=devices, addresses=addresses, bridges=bridges, dns=dns, lease_count=lease_count,
  capabilities=capabilities, services=services,
  routes=read("/proc/net/route"), ipv6routes=read("/proc/net/ipv6_route"),
  tables=read("/proc/net/ip_tables_names"),
  connections=read("/proc/sys/net/netfilter/nf_conntrack_count"):match("%d+") or "Unknown",
  connection_limit=read("/proc/sys/net/netfilter/nf_conntrack_max"):match("%d+") or "Unknown",
  load=read("/proc/loadavg"), memory=read("/proc/meminfo"), mounts=read("/proc/mounts")
 })
end
