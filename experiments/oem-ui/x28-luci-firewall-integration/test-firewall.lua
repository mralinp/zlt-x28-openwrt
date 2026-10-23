-- Run against a staged controller; vendor writes are mocked throughout.
local json = require "luci.jsonc"
local requests, reply, input, code = {}, nil, "", nil
package.loaded["luci.http"] = {
 content = function() return input end,
 prepare_content = function() end,
 status = function(value) code = value end,
 write_json = function(value) reply = value end
}
local state, fail_write, wrong_readback = "1", false, false
package.loaded.vendorbridge = {call = function(body)
 requests[#requests + 1] = body
 assert(body.cmd == 275, "Only DoS protection may be written")
 if body.method == "POST" then
  if fail_write then return {success = false} end
  state = wrong_readback and state or body.ddosSwich
  return {success = true}
 end
 return {success = true, ddosSwich = state}
end}
local path = os.getenv("CONTROLLER_FILE") or "/tmp/x28-firewall-stage/usr/lib/lua/luci/controller/firewall.lua"
dofile(path)
local controller = luci.controller.firewall
local rules = controller.parse_rules([[*mangle
-A INPUT -j MARK
COMMIT
*filter
:INPUT ACCEPT [42:2048]
:FORWARD DROP [0:0]
:OUTPUT ACCEPT [0:0]
:vendor_chain - [0:0]
-A INPUT -j vendor_chain
-A vendor_chain -p tcp --dport 80 -j DROP
COMMIT
*nat
:POSTROUTING ACCEPT [10:500]
-A POSTROUTING -o ccmni1 -j MASQUERADE
COMMIT
]])
assert(rules.available and rules.policies.INPUT == "ACCEPT" and rules.policies.FORWARD == "DROP")
assert(#rules.filter == 2 and #rules.nat == 1 and not rules.policies.vendor_chain)
assert(not controller.parse_rules("").available)
local function call(body)
 requests, reply, code = {}, nil, nil
 input = json.stringify(body)
 controller.action_protection()
 return reply
end
assert(call({enabled = "0"}).success == false and code == 400 and #requests == 0)
assert(call({enabled = true}).success == true and #requests == 1)
assert(call({enabled = false}).success == true and #requests == 3 and requests[2].ddosSwich == "0")
assert(requests[2].cmd == 275 and requests[2].method == "POST")
fail_write = true
assert(call({enabled = true}).success == false and #requests == 2)
fail_write, wrong_readback = false, true
assert(call({enabled = true}).success == false and #requests == 3)
print("PASS: live rule parser; input validation; no-op writes; exact command whitelist; rejected and unverified writes")
