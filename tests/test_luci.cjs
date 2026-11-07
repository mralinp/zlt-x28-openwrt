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
 form: {MultiValue:'multi', DummyValue:'dummy', Button:'button', Value:'value', ListValue:'listvalue', Flag:'flag', DynamicList:'list'},
 fs: {},
 L: {},
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
const tabs = {};
protocol.renderFormOptions({tab: (key, title) => tabs[key] = title, taboption: (tab, _type, key) => options[key] = {tab, deps: [], depends(k, v){this.deps.push([k, v]);}, choices: {}, keylist: [], value(k, v){this.choices[k] = v; this.keylist.push(k);}}});
// A second render on the same section (dialog closed and reopened) must not declare the tab again: form.js throws.
{ let n = 0, opts = 0; const sec = {tab(k) { if (this.tabs && this.tabs[k]) throw 'Tab already declared'; n++; (this.tabs = this.tabs || [])[k] = {}; }, taboption() { opts++; return {depends() {}, value() {}}; }};
  protocol.renderFormOptions(sec); const first = opts; protocol.renderFormOptions(sec);
  if (n !== 1 || opts !== first) throw new Error('second render redeclared the Carrier tab or repeated options'); }
assert.equal(options.apn.validate(null, 'example.invalid'), true);
assert.equal(typeof options.apn.validate(null, 'x;bad'), 'string');
assert.equal(options.apn.validate(null, ''), true);
assert.deepEqual(Object.keys(options.iptype.choices).sort(), ['1', '2', '3']);
assert.equal(options.iptype.default, '3');
assert.equal(tabs.carrier, 'Carrier');
assert.equal(options.roaming.tab, 'carrier');
assert.equal(options.roaming.default, '0');
assert(errors.OPERATOR_FAILED && errors.CELL_LOCK_FAILED && errors.BAND_LOCK_FAILED);
assert.equal(options.x28status.tab, 'carrier');
assert.deepEqual(Object.keys(options.opmode.choices).sort(), ['auto', 'manual']);
assert.equal(options.opmode.default, 'auto');
assert.deepEqual(options.plmn.deps, [['opmode', 'manual']]);
assert.deepEqual(options.plmnscan.deps, [['opmode', 'manual']]);
assert.equal(options.plmn.rmempty, false);
assert.equal(typeof options.plmn.validate(null, ''), 'string');
assert.equal(options.plmn.validate(null, '43211'), true);
assert.equal(options.plmn.validate(null, '432115'), true);
for (const bad of ['4321', '43x11']) assert.equal(typeof options.plmn.validate(null, bad), 'string', bad);
assert.equal(typeof options.plmnscan.onclick, 'function');
const cfgOf = cfg => ({map: {config: 'network', data: {get: () => cfg}}});
for (const [cfg, want] of [['43211', 'manual'], [undefined, 'auto']]) assert.equal(options.opmode.cfgvalue.call(cfgOf(cfg), 'wan'), want);
assert.deepEqual(Object.keys(options.cellmode.choices).sort(), ['lock', 'none']);
assert.deepEqual(options.celllock.deps, [['cellmode', 'lock']]);
assert.equal(options.celllock.rmempty, false);
assert.equal(typeof options.celllock.validate(null, ''), 'string');
assert.equal(options.celllock.validate(null, '42090:258'), true);
assert.equal(options.celllock.validate(null, '46589:511'), true);
for (const bad of ['42090', '46590:258', '42090:512', 'a:1', '1:2:3']) assert.equal(typeof options.celllock.validate(null, bad), 'string', bad);
for (const [cfg, want] of [['42090:258', 'lock'], [undefined, 'none']]) assert.equal(options.cellmode.cfgvalue.call(cfgOf(cfg), 'wan'), want);
assert.deepEqual(Object.keys(options.netmode.choices), ['auto', '4g', '5g']);
assert.equal(options.netmode.default, 'auto');
assert.deepEqual(Object.keys(options.lteband_mode.choices), ['none', 'allow', 'deny']);
assert.equal(options.lteband_mode.default, 'none');
assert.deepEqual(options.lteband_list.deps, [['lteband_mode', 'allow'], ['lteband_mode', 'deny']]);
assert.deepEqual(Object.keys(options.lteband_list.choices), ['1', '3', '5', '7', '8', '20', '28', '32', '38', '40', '41', '42', '43']);
assert.equal(typeof options.lteband_list.validate(null, ''), 'string');
assert.equal(options.lteband_list.validate(null, ['42']), true);
assert.deepEqual(Object.keys(options.nrband_mode.choices), ['none', 'allow', 'deny']);
assert.equal(options.nrband_mode.default, 'none');
assert.deepEqual(options.nrband_list.deps, [['nrband_mode', 'allow'], ['nrband_mode', 'deny']]);
assert.deepEqual(Object.keys(options.nrband_list.choices), ['1', '3', '5', '7', '8', '20', '28', '38', '40', '41', '77', '78']);
assert.equal(typeof options.nrband_list.validate(null, ''), 'string');
assert.equal(options.nrband_list.validate(null, ['78']), true);
assert(errors.NRBAND_LOCK_FAILED);
assert(errors.CONNECT_TIMEOUT && errors.ROAMING_DISABLED && errors.ATTACH_FAILED);
assert.equal(options.mtu.datatype, 'range(576,1500)');
assert.equal(options.metric.datatype, 'range(0,65535)');
assert.equal(options.defaultroute.default, '1');
assert.equal(options.peerdns.default, '1');
assert(errors.VENDOR_WAN_ACTIVE && errors.OWNERSHIP_MISMATCH && errors.CLEANUP_FAILED && errors.NO_SIM_APN && !errors.IPV4_ONLY);
assert(!script.includes('vendorbridge') && !script.includes('http.cgi') && !script.includes('fetch('));
// Every command the page runs through fs.exec must be allowed by the rpcd ACL (a missing entry fails silently in LuCI).
const acl = JSON.parse(fs.readFileSync(path.join(__dirname, '../package/luci-proto-x28-mipc/root/usr/share/rpcd/acl.d/luci-proto-x28-mipc.json'), 'utf8'))['luci-proto-x28-mipc'];
const used = [...script.matchAll(/fs\.exec\('([^']+)'/g)].map(m => m[1]);
assert(used.length >= 3, 'expected the status, scan and apn commands');
for (const cmd of used) assert.deepEqual(acl.read.file[cmd], ['exec'], cmd + ' missing from the ACL read section');
assert.deepEqual(acl.write.file['/sbin/x28-plmn-scan'], ['exec'], 'starting a scan needs write access');
console.log('PASS: native LuCI protocol registration, dynamic device, APN (auto/list/manual) and IP type, routing/DNS fields and error messages');
