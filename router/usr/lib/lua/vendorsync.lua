-- UCI <-> vendor backend adapter. Vendor state is the source of truth on import; UCI edits
-- (LuCI "Save & Apply") are pushed back through vendorbridge on export. Idempotent: only differences are sent.
-- Scope: dhcp.lan (range, lease, DNS), firewall redirects (port forwards) and the DMZ redirect "vendor_dmz".
-- Not mapped (ponytail: add when needed): static leases, network.*, wireless.*, zones/rules, "tcp udp" forwards.
local bridge = require "vendorbridge"
local uci    = require "luci.model.uci".cursor()

local M = {}
local DMZ = "vendor_dmz"

local function log(msg) os.execute("logger -t vendorsync '" .. msg:gsub("'", "") .. "'") end

function M.ip2n(s)
	local a, b, c, d = tostring(s):match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")
	if not a then return nil end
	a, b, c, d = tonumber(a), tonumber(b), tonumber(c), tonumber(d)
	if a > 255 or b > 255 or c > 255 or d > 255 then return nil end
	return ((a * 256 + b) * 256 + c) * 256 + d
end
function M.n2ip(n) return ("%d.%d.%d.%d"):format(math.floor(n / 16777216) % 256, math.floor(n / 65536) % 256, math.floor(n / 256) % 256, n % 256) end

-- "12h" "30m" "2d" "7200" -> whole hours (>=1), nil if infinite/unparseable
function M.hours(s)
	local n, u = tostring(s or ""):match("^(%d+)([smhd]?)$")
	if not n then return nil end
	local sec = tonumber(n) * ({s = 1, m = 60, h = 3600, d = 86400, [""] = 1})[u]
	return math.max(1, math.floor(sec / 3600 + 0.5))
end

local function lan_info()
	local l = bridge.call({cmd = 3, method = "GET"})
	if not l.success then return nil, "vendor LAN read failed" end
	local ip, mask = M.ip2n(l.lanIp), M.ip2n(l.netMask)
	if not ip or not mask then return nil, "bad LAN address" end
	local size = 4294967296 - mask   -- contiguous mask: block size
	return l, ip - ip % size, size, ip
end

local function strip(t) for _, k in ipairs({"success", "sessionId", "token", "message"}) do t[k] = nil end return t end

-- ---------- import: vendor -> UCI ----------
function M.import()
	if #(uci:changes("dhcp")) + #(uci:changes("firewall")) > 0 then return log("import skipped: pending UCI changes") end
	local l, base = lan_info()
	if not l then return log(base) end
	local b, e = M.ip2n(l.ipBegin), M.ip2n(l.ipEnd)
	if b and e and e >= b then
		uci:set("dhcp", "lan", "start", tostring(b - base))
		uci:set("dhcp", "lan", "limit", tostring(e - b + 1))
	end
	uci:set("dhcp", "lan", "leasetime", l.expireTime ~= "" and l.expireTime or "24h")
	if l.dhcpServer == "1" then uci:delete("dhcp", "lan", "ignore") else uci:set("dhcp", "lan", "ignore", "1") end
	local dns = {}
	for _, k in ipairs({"main_dns", "vice_dns"}) do if l[k] and l[k] ~= "" then dns[#dns + 1] = l[k] end end
	if #dns > 0 then uci:set_list("dhcp", "lan", "dhcp_option", {"6," .. table.concat(dns, ",")}) end
	uci:commit("dhcp")

	-- port forwards: replace every wan->lan DNAT redirect with the vendor list
	uci:foreach("firewall", "redirect", function(s)
		if s[".name"] ~= DMZ and s.src == "wan" and s.dest == "lan" and s.src_dport then uci:delete("firewall", s[".name"]) end
	end)
	local pf = bridge.call({cmd = 27, method = "GET", getfun = true})
	for i, r in ipairs(pf.datas or {}) do
		local n = "vendor_pf" .. i
		uci:section("firewall", "redirect", n, {name = r.remark ~= "" and r.remark or n, src = "wan", dest = "lan", target = "DNAT",
			proto = (r.protocol or "TCP"):lower(), src_dport = r.port, dest_ip = r.mappingIp, dest_port = r.mappingPort,
			enabled = r.enableRule and "1" or "0"})
	end
	local d = bridge.call({cmd = 172, method = "GET", subcmd = 6})
	uci:delete("firewall", DMZ)
	if d.ip and d.ip ~= "" then
		uci:section("firewall", "redirect", DMZ, {name = "DMZ", src = "wan", dest = "lan", target = "DNAT", proto = "all",
			dest_ip = d.ip, enabled = d.enabled == "1" and "1" or "0"})
	end
	uci:commit("firewall")
	log(("imported: %d port forwards, dmz=%s"):format(#(pf.datas or {}), tostring(d.ip)))
end

-- ---------- export: UCI -> vendor ----------
local function export_dhcp()
	local l, base, size, lanip = lan_info()
	if not l then return log(base) end
	local s = uci:get_all("dhcp", "lan") or {}
	local start, limit = tonumber(s.start), tonumber(s.limit)
	local hrs = M.hours(s.leasetime)
	if not (start and limit and hrs and limit >= 1) then return log("dhcp export skipped: start/limit/leasetime not usable") end
	local b, e = base + start, base + start + limit - 1
	if b <= base or e >= base + size - 1 or (lanip >= b and lanip <= e) then return log("dhcp export refused: range outside subnet or covers the router") end
	local dns = {}
	local opt = s.dhcp_option
	if type(opt) == "string" then opt = {opt} end
	for _, o in ipairs(opt or {}) do local v = o:match("^6,(.+)$"); if v then for ip in v:gmatch("[^,]+") do dns[#dns + 1] = ip end end end
	local want = {dhcpServer = s.ignore == "1" and "0" or "1", ipBegin = M.n2ip(b), ipEnd = M.n2ip(e), expireTime = hrs .. "h",
		main_dns = dns[1] or l.main_dns, vice_dns = dns[2] or ""}
	local diff = false
	for k, v in pairs(want) do if tostring(l[k]) ~= v then diff = true end end
	if not diff then return end
	local body = {}
	for k, v in pairs(l) do body[k] = v end
	strip(body)
	for k, v in pairs(want) do body[k] = v end
	body.cmd, body.method = 3, "POST"
	local r = bridge.call(body)
	log("dhcp export: " .. tostring(r.success or r.flag))
end

local function export_firewall()
	local want = {}
	uci:foreach("firewall", "redirect", function(s)
		if s[".name"] ~= DMZ and s.src == "wan" and s.src_dport and s.dest_ip and s.dest_port and (s.target or "DNAT") == "DNAT" then
			local p = tostring(s.proto or "tcp"):lower()
			if p == "tcp" or p == "udp" then
				want[#want + 1] = {port = s.src_dport, mappingIpPort = s.dest_ip .. ":" .. s.dest_port, mappingIp = s.dest_ip,
					mappingPort = s.dest_port, remark = s.name or "", enableRule = s["enabled"] ~= "0", protocol = p:upper(), ifName = "DEFAULT"}
			else log("skipped forward '" .. tostring(s.name) .. "': proto " .. p .. " not supported by vendor backend") end
		end
	end)
	local cur = bridge.call({cmd = 27, method = "GET", getfun = true}).datas or {}
	local function key(t) local o = {} for _, r in ipairs(t) do o[#o + 1] = table.concat({r.port, r.mappingIp, r.mappingPort, r.protocol, r.remark, tostring(r.enableRule)}, "|") end table.sort(o) return table.concat(o, "\n") end
	if key(want) ~= key(cur) then
		if #want > 32 then return log("forward export refused: more than 32 rules") end
		local r = bridge.call({cmd = 27, method = "POST", success = true, datas = want})
		if r.success == 1 or r.success == true then bridge.call({cmd = 20, method = "POST"}) end
		log("forward export: " .. #want .. " rules, ok=" .. tostring(r.success))
	end

	local d = uci:get_all("firewall", DMZ)
	local en, ip = (d and d.enabled ~= "0") and "1" or "0", d and d.dest_ip or ""
	local lan = lan_info()
	if en == "1" and (not M.ip2n(ip) or not lan or ip == lan.lanIp) then return log("dmz export refused: bad ip") end
	local cd = bridge.call({cmd = 172, method = "GET", subcmd = 6})
	if (cd.enabled or "0") ~= en or (en == "1" and cd.ip ~= ip) then
		local r = bridge.call({cmd = 172, method = "POST", subcmd = 6, enabled = en, ip = en == "1" and ip or ""})
		log("dmz export: enabled=" .. en .. " ok=" .. tostring(r.success))
	end
end

function M.export() export_dhcp(); export_firewall() end

function M.selftest()
	assert(M.ip2n("192.168.70.1") == 3232253441 and M.n2ip(3232253441) == "192.168.70.1")
	assert(M.ip2n("300.1.1.1") == nil and M.ip2n("x") == nil)
	assert(M.hours("24h") == 24 and M.hours("90m") == 2 and M.hours("1d") == 24 and M.hours("infinite") == nil)
	print("selftest ok")
end

return M
