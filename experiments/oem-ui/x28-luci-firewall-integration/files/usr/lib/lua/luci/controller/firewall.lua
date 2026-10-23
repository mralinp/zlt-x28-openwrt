module("luci.controller.firewall", package.seeall)

function index()
 entry({"admin", "network", "firewall"}, alias("admin", "network", "firewall", "zones"), _("Firewall"), 60)
 entry({"admin", "network", "firewall", "zones"}, template("vendor/firewall"), _("General Settings"), 10)
 entry({"admin", "network", "firewall", "forwards"}, template("vendor/portforward"), _("Port Forwards"), 20)
 entry({"admin", "network", "firewall", "dmz"}, template("vendor/dmz"), _("DMZ"), 30)
 -- Stock fw3 editors would rebuild vendor-managed chains using stale UCI zones.
 for _, name in ipairs({"rules", "snats", "custom"}) do
  entry({"admin", "network", "firewall", name}, alias("admin", "network", "firewall", "zones"))
 end
 entry({"admin", "network", "firewall", "status"}, call("action_status")).leaf = true
 entry({"admin", "network", "firewall", "protection"}, post("action_protection")).leaf = true
end

function parse_rules(text)
 local result = {available = false, policies = {}, filter = {}, nat = {}}
 local section
 for line in (text or ""):gmatch("[^\n]+") do
  if line:sub(1, 1) == "*" then section = line:sub(2)
  elseif line == "COMMIT" then section = nil
  elseif section == "filter" or section == "nat" then
   if section == "filter" then result.available = true end
   local name, policy = line:match("^:(%S+)%s+(%S+)")
   if section == "filter" and policy ~= "-" and (name == "INPUT" or name == "FORWARD" or name == "OUTPUT") then
    result.policies[name] = policy
   end
   if line:match("^-A ") then table.insert(result[section], line) end
  end
 end
 return result
end

function action_status()
 local bridge, sys = require "vendorbridge", require "luci.sys"
 local firewall = bridge.call({cmd = 367, method = "GET"})
 local protection = bridge.call({cmd = 275, method = "GET"})
 require("luci.http").prepare_content("application/json")
 require("luci.http").write_json({
  firewall = {success = firewall.success, enabled = firewall.fw_switch, level = firewall.level},
  protection = {success = protection.success, enabled = protection.ddosSwich, ack = protection.ackFloodSwich},
  ipv4 = parse_rules(sys.exec("iptables-save 2>/dev/null")),
  ipv6 = parse_rules(sys.exec("ip6tables-save 2>/dev/null"))
 })
end

function action_protection()
 local http, json = require "luci.http", require "luci.jsonc"
 local body = json.parse(http.content() or "")
 http.prepare_content("application/json")
 if type(body) ~= "table" or type(body.enabled) ~= "boolean" then
  http.status(400, "Bad Request")
  http.write_json({success = false, message = "Enabled must be a boolean"})
  return
 end
 local bridge = require "vendorbridge"
 local before = bridge.call({cmd = 275, method = "GET"})
 local value = body.enabled and "1" or "0"
 if before.success ~= true or (before.ddosSwich ~= "0" and before.ddosSwich ~= "1") then
  http.write_json({success = false, message = "Cannot read the current protection state; no change was sent"})
  return
 end
 if before.ddosSwich == value then
  http.write_json({success = true, message = "Protection is already set to this value"})
  return
 end
 local reply = bridge.call({cmd = 275, method = "POST", ddosSwich = value})
 if reply.success ~= true and reply.success ~= 1 then
  http.write_json({success = false, message = "The modem did not confirm the change; refresh to check its current state"})
  return
 end
 local after = bridge.call({cmd = 275, method = "GET"})
 local verified = after.success == true and after.ddosSwich == value
 http.write_json({success = verified, message = verified and "Protection updated and verified" or "The write was accepted, but the current state could not be verified; refresh before retrying"})
end
