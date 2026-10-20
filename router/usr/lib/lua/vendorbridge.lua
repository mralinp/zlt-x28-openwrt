-- Proxy to the vendor backend (/tzwww/cgi-bin/http.cgi). Logs in with /etc/vendor-ui.cred
-- (line 1 = username, line 2 = password) and caches the session in /tmp/vendor.sess.
local jsonc = require "luci.jsonc"
local sys   = require "luci.sys"
local fs    = require "nixio.fs"

local M = {}
local CGI, CRED, SESS = "/tzwww/cgi-bin/http.cgi", "/etc/vendor-ui.cred", "/tmp/vendor.sess"

local function raw(tbl)
	local f = os.tmpname()
	local body = jsonc.stringify(tbl)
	fs.writefile(f, body)
	local p = io.popen(("REQUEST_METHOD=POST CONTENT_TYPE=application/json CONTENT_LENGTH=%d %s < %s 2>/dev/null")
		:format(#body, CGI, f))
	local out = p:read("*a"); p:close(); fs.remove(f)
	return jsonc.parse(out:match("\r?\n\r?\n(.*)$") or out:match("{.*}") or "") or {}
end

local function login()
	local c = fs.readfile(CRED)
	local user, pw = (c or ""):match("^([^\n]*)\n([^\n]*)")
	if not user or user == "" then return nil, "missing " .. CRED end
	local t = raw({cmd = 232, method = "GET", sessionId = "", language = "EN"}).token
	if not t then return nil, "no login token" end
	local f = os.tmpname(); fs.writefile(f, t .. pw); fs.chmod(f, 600)
	local hash = sys.exec("sha256sum " .. f):match("^(%x+)"); fs.remove(f)
	local sid = sys.uniqueid(16) .. sys.uniqueid(16)
	local r = raw({cmd = 100, method = "POST", sessionId = sid, username = user, passwd = hash,
		isAutoUpgrade = "0", subcmd = 0, language = "EN"})
	if r.login_fail == "fail" or not r.sessionId then return nil, "vendor login failed" end
	local tok = raw({cmd = 233, method = "GET", sessionId = r.sessionId, language = "EN"}).token or ""
	fs.writefile(SESS, r.sessionId .. "\n" .. tok); fs.chmod(SESS, 600)
	return r.sessionId, tok
end

local function session()
	local s = fs.readfile(SESS)
	if s then local a, b = s:match("^([^\n]*)\n([^\n]*)"); if a and a ~= "" then return a, b end end
	return login()
end

-- body: table with at least cmd; returns the vendor reply table
function M.call(body)
	body.language = "EN"; body.method = body.method or "GET"
	for attempt = 1, 2 do
		local sid, tok = session()
		if not sid then return {success = false, message = tok} end
		body.sessionId, body.token = sid, tok
		local r = raw(body)
		if r.message ~= "NO_AUTH" then return r end
		fs.remove(SESS)
	end
	return {success = false, message = "NO_AUTH"}
end

return M
