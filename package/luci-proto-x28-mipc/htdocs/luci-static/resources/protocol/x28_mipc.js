// SPDX-License-Identifier: GPL-2.0-only
'use strict';
'require form';
'require fs';
'require network';

network.registerPatternVirtual(/^ccmni[0-9]+$/);
[
 ['INVALID_CONFIG', 'Invalid APN, IP type, MTU or routing options'],
 ['NO_SIM_APN', 'No APN is known for this SIM; choose or enter one'],
 ['NO_IPV6', 'The network sent no IPv6 prefix'],
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
 getI18n: function() { return _('X28 5G modem (MIPC)'); },
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
   _('Leave empty to use the SIM\'s APN automatically, pick one of the SIM\'s APNs, or type one. No PAP/CHAP.'));
  option.placeholder = _('Automatic (from SIM)');
  option.validate = function(_section, value) {
   return /^[A-Za-z0-9._-]{0,100}$/.test(value || '') || _('Enter an APN of up to 100 letters, digits, dots, underscores or hyphens.');
  };
  option.load = function(section_id) {
   // x28-apn prints "carrier<TAB>apn<TAB>ipVersion" per APN known for the inserted SIM.
   return fs.exec('/sbin/x28-apn').then(L.bind(function(res) {
    (res.stdout || '').split('\n').forEach(L.bind(function(line) {
     var f = line.split('\t');
     if (f[1]) this.value(f[1], '%s (%s)'.format(f[1], f[0] || _('SIM')));
    }, this));
   }, this)).catch(function() {}).then(L.bind(form.Value.prototype.load, this, section_id));
  };
  option = section.taboption('general', form.ListValue, 'iptype', _('IP type'));
  option.value('3', _('IPv4/IPv6'));
  option.value('1', _('IPv4 only'));
  option.value('2', _('IPv6 only'));
  option.default = '3';
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
