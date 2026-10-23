// SPDX-License-Identifier: GPL-2.0-only
'use strict';
'require form';
'require network';

network.registerPatternVirtual(/^ccmni[0-9]+$/);
[
 ['INVALID_CONFIG', 'Invalid APN, MTU or routing options'],
 ['IPV4_ONLY', 'This experimental protocol currently supports IPv4 only'],
 ['VENDOR_WAN_ACTIVE', 'The vendor WAN manager is active; native ownership is not established'],
 ['MODEM_BUSY', 'Another modem operation is in progress'],
 ['MISSING_MODEM_CLI', 'The required MIPC modem utility is unavailable'],
 ['SIM_PIN_LOCKED', 'The SIM requires PIN or PUK handling'],
 ['SIM_NOT_READY', 'The SIM is not ready'],
 ['CONNECT_FAILED', 'The modem could not establish the data connection'],
 ['INVALID_REPLY', 'The modem returned an invalid bearer response'],
 ['LINK_NOT_READY', 'The reported bearer device is not up'],
 ['NOTIFY_FAILED', 'The connection could not be reported to netifd'],
 ['CLEANUP_FAILED', 'The new bearer could not be cleaned up; inspect the modem before retrying'],
 ['OWNERSHIP_MISMATCH', 'Bearer ownership could not be verified'],
 ['STATUS_UNAVAILABLE', 'The interface status could not be read'],
 ['DEACTIVATE_FAILED', 'The modem did not confirm bearer teardown']
].forEach(function(error) { network.registerErrorCode(error[0], _(error[1])); });

return network.registerProtocol('x28_mipc', {
 getI18n: function() { return _('X28 MIPC (experimental IPv4)'); },
 getIfname: function() { return this._ubus('l3_device') || null; },
 getOpkgPackage: function() { return 'x28-mipc'; },
 isFloating: function() { return true; },
 isVirtual: function() { return true; },
 getDevices: function() { return null; },
 containsDevice: function(ifname) {
  var device = this.getIfname();
  return device != null && network.getIfnameOf(ifname) === device;
 },
 renderFormOptions: function(section) {
  var option = section.taboption('general', form.Value, 'apn', _('APN'),
   _('IPv4 routing with no PAP/CHAP. Requires a pre-initialized modem and native network ownership.'));
  option.rmempty = false;
  option.validate = function(_section, value) {
   return /^[A-Za-z0-9._-]{1,100}$/.test(value || '') || _('Enter an APN of 1–100 letters, digits, dots, underscores or hyphens.');
  };
  option = section.taboption('advanced', form.Value, 'mtu', _('MTU'));
  option.datatype = 'range(576,1500)';
  option.placeholder = '1500';
  option = section.taboption('advanced', form.Flag, 'defaultroute', _('Use default gateway'));
  option.default = '1';
  option = section.taboption('advanced', form.Flag, 'peerdns', _('Use DNS servers advertised by peer'));
  option.default = '1';
  option = section.taboption('advanced', form.DynamicList, 'dns', _('Use custom DNS servers'));
  option.depends('peerdns', '0');
  option.datatype = 'ipaddr';
  option = section.taboption('advanced', form.Value, 'metric', _('Gateway metric'));
  option.datatype = 'range(0,65535)';
  option.placeholder = '0';
 }
});
