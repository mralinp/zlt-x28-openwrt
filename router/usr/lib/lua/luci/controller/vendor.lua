module("luci.controller.vendor", package.seeall)

local jsonc = require "luci.jsonc"
local http  = require "luci.http"

function index()
	entry({"admin", "vendor"}, firstchild(), _("Vendor"), 60).dependent = false
	entry({"admin", "vendor", "lan"},   template("vendor/lan"),   _("LAN / DHCP"), 1)
	entry({"admin", "vendor", "wifi"},  template("vendor/wifi"),  _("WiFi"), 2)
	entry({"admin", "vendor", "portforward"}, template("vendor/portforward"), _("Port forwarding"), 5)
	entry({"admin", "vendor", "dmz"},   template("vendor/dmz"),   _("DMZ"), 10)
	entry({"admin", "vendor", "sms"},   template("vendor/sms"),   _("SMS"), 20)
	entry({"admin", "vendor", "voice"}, template("vendor/voice"), _("Voice"), 30)
	entry({"admin", "vendor", "ussd"},  template("vendor/ussd"),  _("USSD"), 25)
	entry({"admin", "vendor", "call"},  call("action_call")).leaf = true
	entry({"admin", "vendor", "voicectl"}, call("action_voicectl")).leaf = true
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
