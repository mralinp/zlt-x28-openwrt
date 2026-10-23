// SPDX-License-Identifier: GPL-2.0-only
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '../package/luci-proto-x28-mipc/htdocs/luci-static/resources/protocol/x28_mipc.js'), 'utf8');
const errors = {}, options = {};
let name;
const protocol = vm.runInNewContext('(function(){' + script + '\n})()', {
 _: value => value,
 form: {Value:'value', Flag:'flag', DynamicList:'list'},
 network: {
  registerPatternVirtual: pattern => assert(pattern.test('ccmni7') && !pattern.test('eth0')),
  registerErrorCode: (key, value) => errors[key] = value,
  registerProtocol: (key, value) => {name = key;return value;},
  getIfnameOf: value => value
 }
});
assert.equal(name, 'x28_mipc');
assert.equal(protocol.getOpkgPackage(), 'x28-mipc');
protocol._ubus = () => undefined;
assert.equal(protocol.getIfname(), null);
assert.equal(protocol.containsDevice('ccmni0'), false);
protocol._ubus = () => 'ccmni7';
assert.equal(protocol.getIfname(), 'ccmni7');
assert.equal(protocol.containsDevice('ccmni7'), true);
assert.equal(protocol.containsDevice('ccmni1'), false);
protocol.renderFormOptions({taboption: (_tab, _type, key) => options[key] = {depends(){}}});
assert.equal(options.apn.validate(null, 'example.invalid'), true);
assert.equal(typeof options.apn.validate(null, 'x;bad'), 'string');
assert.equal(typeof options.apn.validate(null, ''), 'string');
assert.equal(options.mtu.datatype, 'range(576,1500)');
assert.equal(options.metric.datatype, 'range(0,65535)');
assert.equal(options.defaultroute.default, '1');
assert.equal(options.peerdns.default, '1');
assert(errors.VENDOR_WAN_ACTIVE && errors.OWNERSHIP_MISMATCH && errors.CLEANUP_FAILED);
assert(!script.includes('vendorbridge') && !script.includes('http.cgi') && !script.includes('fetch('));
console.log('PASS: native LuCI protocol registration, dynamic device, APN validation, routing/DNS fields and error messages');
