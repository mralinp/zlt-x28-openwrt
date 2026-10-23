module("luci.controller.vendor", package.seeall)

local jsonc = require "luci.jsonc"
local http  = require "luci.http"

function index()
	-- Keep old URLs and API callers working without a second navigation tree.
	entry({"admin", "vendor"}, alias("admin", "network", "network")).dependent = false
	entry({"admin", "vendor", "lan"}, alias("admin", "network", "dhcp"))
	entry({"admin", "vendor", "wifi"}, alias("admin", "network", "wireless"))
	for index, page in ipairs({{"portforward", "forwards"}, {"dmz", "dmz"}}) do
		entry({"admin", "network", page[1]}, alias("admin", "network", "firewall", page[2]))
		entry({"admin", "vendor", page[1]}, alias("admin", "network", "firewall", page[2]))
	end
	for index, page in ipairs({{"sms", "SMS", 20}, {"ussd", "USSD", 25}, {"voice", "Voice", 30}}) do
		entry({"admin", "services", page[1]}, template("vendor/" .. page[1]), _(page[2]), page[3])
		entry({"admin", "vendor", page[1]}, alias("admin", "services", page[1]))
	end
	entry({"admin", "vendor", "call"}, call("action_call")).leaf = true
	entry({"admin", "vendor", "voicectl"}, call("action_voicectl")).leaf = true
	entry({"admin", "network", "x28_status"}, call("action_network_status")).leaf = true
end

-- POST /admin/vendor/call  body: JSON {cmd=..., ...}; LuCI checks the CSRF token field via the query string.
function action_call()
	local body = jsonc.parse(http.content() or "")
	http.prepare_content("application/json")
	if type(body) ~= "table" or type(body.cmd) ~= "number" then
		http.write('{"success":false,"message":"bad request"}'); return
	end
	body.token, body.sessionId = nil, nil
	http.write(jsonc.stringify(require("vendorbridge").call(body)))
end

local function sh(cmd)
	local p = io.popen(cmd .. " 2>&1"); local o = p:read("*a"); p:close(); return o
end

-- POST JSON {action=dial|answer|hangup|status|stop, number=...}
function action_voicectl()
	local b = jsonc.parse(http.content() or "") or {}
	local a, n = tostring(b.action or ""), tostring(b.number or "")
	http.prepare_content("application/json")
	local cmd
	if a == "dial" and n:match("^%+?%d+$") and #n <= 20 then cmd = "voicectl dial " .. n
	elseif a == "answer" or a == "hangup" or a == "stop" then cmd = "voicectl " .. a
	elseif a ~= "status" then http.write('{"success":false,"message":"bad request"}'); return end
	local out = cmd and sh(cmd) or ""
	local ims = sh("atcmd 'AT+CIREG?'"):match("%+CIREG: (%d,%d)") or "?"
	local clcc = sh("atcmd 'AT+CLCC'"):gsub("^recv:%s*", ""):gsub("%s*OK%s*$", "")
	http.write(jsonc.stringify({success = true, ims = ims, calls = clcc, out = out,
		log = sh("voicectl status 15")}))
end

-- Runtime data only: do not derive live topology from the stale UCI files.
function action_network_status()
	local fs = require "nixio.fs"
	local interfaces, order = {}, {}
	for _, a in ipairs(require("nixio").getifaddrs() or {}) do
		if a.name ~= "lo" then
			if not interfaces[a.name] then
				interfaces[a.name] = {name = a.name, up = a.flags and a.flags.up or false, addresses = {}}
				table.insert(order, a.name)
			end
			local i = interfaces[a.name]
			if a.family == "inet" or a.family == "inet6" then
				table.insert(i.addresses, a.addr .. "/" .. tostring(a.prefix))
			end
			if a.family == "packet" then i.stats = a.data end
		end
	end
	local defaults = {}
	for line in (fs.readfile("/proc/net/route") or ""):gmatch("[^\n]+") do
		local dev, dest, gateway, flags = line:match("^(%S+)%s+(%x+)%s+(%x+)%s+(%x+)")
		if dest == "00000000" and tonumber(flags, 16) % 2 == 1 then defaults[dev] = true end
	end
	local result = {}
	table.sort(order)
	for _, name in ipairs(order) do
		local i = interfaces[name]
		if fs.access("/sys/class/net/" .. name .. "/bridge") then
			i.members = {}
			for member in fs.dir("/sys/class/net/" .. name .. "/brif") do table.insert(i.members, member) end
			table.sort(i.members)
		end
		i.default_route = defaults[name] or false
		if i.up or #i.addresses > 0 or i.members then table.insert(result, i) end
	end
	http.prepare_content("application/json")
	http.write_json({interfaces = result})
end
