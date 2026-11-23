// SPDX-License-Identifier: GPL-2.0-only
'use strict';
'require form';
'require fs';
'require ui';
'require network';

network.registerPatternVirtual(/^ccmni[0-9]+$/);
[
 ['INVALID_CONFIG', 'Invalid APN, IP type, roaming, operator, cell lock, bands, MTU or routing options'],
 ['NO_SIM_APN', 'No APN is known for this SIM; choose or enter one'],
 ['ROAMING_DISABLED', 'Registered on a roaming network and roaming is off; enable Allow roaming'],
 ['ATTACH_FAILED', 'The modem could not re-attach with this APN and IP type'],
 ['NO_IPV6', 'The network sent no IPv6 prefix'],
 ['VENDOR_WAN_ACTIVE', 'The vendor WAN manager is active; native ownership is not established'],
 ['MODEM_BUSY', 'Another modem operation is in progress'],
 ['MISSING_MODEM_CLI', 'The required MIPC modem utility is unavailable'],
 ['SIM_PIN_LOCKED', 'The SIM requires PIN or PUK handling'],
 ['SIM_NOT_READY', 'The SIM is not ready'],
 ['CONNECT_FAILED', 'The modem could not establish the data connection'],
 ['CONNECT_TIMEOUT', 'The modem did not answer the data call; the radio was restarted and it will retry'],
 ['OPERATOR_FAILED', 'The chosen operator did not register; the modem was set back to automatic'],
 ['CELL_LOCK_FAILED', 'The cell lock did not take effect on the modem'],
 ['BAND_LOCK_FAILED', 'The band lock did not take effect on the modem'],
 ['NETMODE_FAILED', 'The network mode did not take effect on the modem'],
 ['NRBAND_LOCK_FAILED', 'The 5G band lock did not take effect on the modem, or the band tool (x28-nrband) is missing'],
 ['INVALID_REPLY', 'The modem returned an invalid bearer response'],
 ['LINK_NOT_READY', 'The reported bearer device is not up'],
 ['NOTIFY_FAILED', 'The connection could not be reported to netifd'],
 ['CLEANUP_FAILED', 'The new bearer could not be cleaned up; inspect the modem before retrying'],
 ['OWNERSHIP_MISMATCH', 'Bearer ownership could not be verified'],
 ['STATUS_UNAVAILABLE', 'The interface status could not be read'],
 ['DEACTIVATE_FAILED', 'The modem did not confirm bearer teardown'],
 ['PASSTHROUGH_FAILED', 'IPv4 passthrough could not be set up (address on the LAN, or DHCP/firewall failed); see the system log']
].forEach(function(error) { network.registerErrorCode(error[0], _(error[1])); });

// wan6 of the cellular WAN (#648): IPv6 of the bearer that the x28_mipc interface named in its device ('@wan') owns; no options of its own.
network.registerProtocol('x28_mipc6', {
 getI18n: function() { return _('X28 5G modem IPv6 (companion of the MIPC interface)'); },
 getIfname: function() { return this._ubus('l3_device') || null; },
 getOpkgPackage: function() { return 'x28-mipc'; },
 isFloating: function() { return false; },
 isVirtual: function() { return false; },
 renderFormOptions: function(section) {
  var option = section.taboption('advanced', form.Flag, 'defaultroute', _('Use default gateway'));
  option.default = '1';
  option = section.taboption('advanced', form.Flag, 'peerdns', _('Use DNS servers advertised by peer'));
  option.default = '1';
  option = section.taboption('advanced', form.Value, 'metric', _('Gateway metric'));
  option.datatype = 'range(0,65535)';
  option.placeholder = '0';
 }
});

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
  // Carrier-related vendor settings (roaming now; operator, network mode, bands, PCI lock later) live together here.
  // Every dialog open builds a new section that shares the interface list's tab table (form.js: s.tabs = this.tabs), so the
  // tab can already exist from an earlier open; declaring it again throws, and skipping all options leaves the tab empty and hidden.
  if (!(section.tabs && section.tabs.carrier)) section.tab('carrier', _('Carrier'));
  // One call of the read-only status helper per page load; its lines are "key<TAB>value...".
  var modemStatus = function() {
   return modemStatus.cache || (modemStatus.cache = fs.exec('/sbin/x28-modem-status').then(function(res) {
    var out = { info: [], cells: [] };
    (res.stdout || '').split('\n').forEach(function(line) {
     var f = line.split('\t');
     if (f[0] == 'serving' || f[0] == 'cell' || f[0] == 'nrcell') out.cells.push({ serving: f[0] == 'serving', nr: f[0] == 'nrcell', id: f[1], band: f[2], rsrp: f[3], rsrq: f[4] });
     else if (f[0] == 'nrsig') out.nrsig = f;
     else if (f[0]) out.info.push(f);
    });
    return out;
   }).catch(function(e) {
    ui.addNotification(null, E('p', _('Could not read the modem state: %s').format(e.message || e)), 'danger');
    return { info: [], cells: [] };
   }));
  };
  modemStatus.cache = null;
  option = section.taboption('carrier', form.DummyValue, 'x28status', _('Modem status'));
  option.rawhtml = true;
  option.load = function() {
   return modemStatus().then(L.bind(function(st) {
    var esc = function(v) { return String(v).replace(/&/g, '&amp;').replace(/</g, '&lt;'); };
    var rat = { lte: '4G', lte_ca: '4G with carrier aggregation', endc: '4G + 5G (EN-DC)', nr: '5G', other: 'other' };
    var text = st.info.map(function(f) { return f[0] == 'rat' ? 'network: %s'.format(rat[f[1]] || f[1]) : '%s: %s'.format(f[0], f[1] || '-'); });
    if (st.nrsig) text.push('5G signal: RSRP %s dBm, RSRQ %s dB'.format(st.nrsig[1], st.nrsig[2]));
    st.cells.forEach(function(c) {
     text.push('%s: %s %s, band %s, %s'.format(c.serving ? 'serving cell' : (c.nr ? '5G cell' : 'cell'), c.nr ? 'NR-ARFCN:PCI' : 'EARFCN:PCI', c.id, c.band,
      c.rsrp == '?' ? 'no measurement' : 'RSRP %s dBm, RSRQ %s dB'.format(c.rsrp, c.rsrq)));
    });
    this.status = '<pre>' + esc(text.join('\n') || _('Modem status unavailable')) + '</pre>';
   }, this));
  };
  option.cfgvalue = function() { return this.status; };
  // Auto-tune (x28-autotune): resets the settings below, tries automatic, 4G only and each seen 4G band, keeps the most bandwidth.
  // Results and state are read as files: read-only users may see them, only writers may run x28-autotune (ACL).
  var tuneRead = function(file) {
   return fs.read(file).catch(function() { return ''; }).then(function(text) { return { stdout: text || '' }; });
  };
  // fs.exec resolves on a non-zero exit too; x28-autotune says why on stderr (e.g. uncommitted network changes).
  var tuneExec = function(arg) {
   return fs.exec('/sbin/x28-autotune', [arg]).then(function(res) {
    if (res.code) throw new Error((res.stderr || '').trim() || 'exit code %d'.format(res.code));
    return res;
   });
  };
  var tuneRows = function(res, full) {
   return (res.stdout || '').split('\n').filter(function(l) { return l; }).map(function(l) {
    var f = l.split('\t');
    if (f[0] == 'best') return _('Kept: %s').format(f[1] || _('automatic (no configuration reached the speed-test servers)'));
    // The last field is "<sample>/<sample>", or why there are none: refused (the network refused the SIM), no connection.
    if (f[5] && f[5].indexOf('/') < 0) return '%s: %s'.format(f[0], f[5] == 'refused' ? _('refused this SIM') : _('no connection'));
    return full ? '%s: %s Mbit/s (samples %s), %s, RSRP %s, CA %s'.format(f[0], f[1], f[5] || '-', f[2], f[3], f[4] || '-') : '%s: %s Mbit/s, CA %s'.format(f[0], f[1], f[4] || '-');
   }).join('\n');
  };
  option = section.taboption('carrier', form.Button, 'autotune', _('Auto-tune'),
   _('Resets the settings below (roaming on, automatic operator, mode and bands, no cell lock), then searches for networks and tries each one this SIM may use (a virtual or roaming SIM may be allowed on several), and on the best of them 4G only and locks to pairs and single 4G bands the modem sees (a pair keeps carrier aggregation possible, a single band does not). It measures the download bandwidth of each twice and keeps the one with the most; a network, lock or mode other than automatic is kept only when it beats automatic by 15% or more. Takes up to about 30 minutes; the connection drops at every step and each step downloads twice for 8 s from the nearest speedtest.net servers (on a fast link that is about 200 MB per step).'));
  option.inputtitle = _('Auto-tune');
  option.inputstyle = 'apply';
  option.onclick = function() {
   var log = E('pre', {}, _('Resetting and waiting for the first connection...'));
   var stopped = false;
   var poll = function() {
    return tuneRead('/tmp/x28-autotune').then(function(res) {
     log.textContent = tuneRows(res, true) || _('Resetting and waiting for the first connection...');
     return tuneRead('/tmp/x28-autotune.state');
    }).then(function(res) {
     if (stopped) return;
     if ((res.stdout || '').trim() !== 'running') { window.location.reload(); return; }
     return new Promise(function(resolve) { window.setTimeout(resolve, 5000); }).then(poll);
    });
   };
   return new Promise(function(resolve) {
    ui.showModal(_('Auto-tune'), [
     E('p', _('This resets your Carrier settings, turns roaming on (roaming may cost money) and drops the connection several times. The previous settings can be restored afterwards.')),
     E('div', { 'class': 'right' }, [
      E('button', { 'class': 'btn', 'click': function() { ui.hideModal(); resolve(); } }, _('Cancel')), ' ',
      E('button', { 'class': 'btn cbi-button-apply', 'click': function() {
       ui.showModal(_('Auto-tune running'), [log, E('div', { 'class': 'right' }, E('button', { 'class': 'btn cbi-button-negative', 'click': function() {
        stopped = true;
        tuneExec('--stop').catch(function(e) { window.alert(_('Could not restore: %s').format(e.message || e)); }).finally(function() { window.location.reload(); });
       } }, _('Stop and restore')))]);
       tuneExec('--start').then(poll).catch(function(e) {
        ui.hideModal();
        ui.addNotification(null, E('p', _('Auto-tune could not be started: %s').format(e.message || e)), 'danger');
       }).then(resolve);
      } }, _('Start'))
     ])
    ]);
   });
  };
  option = section.taboption('carrier', form.Button, 'autotune_restore', _('Before auto-tune'),
   _('Puts back the Carrier settings that were in place before the last auto-tune.'));
  option.inputtitle = _('Restore');
  option.load = function() {
   return tuneRead('/tmp/x28-autotune').then(L.bind(function(res) {
    var rows = tuneRows(res, false);
    if (rows) this.description = _('Puts back the Carrier settings that were in place before the last auto-tune. Its results:') + '\n' + rows;
   }, this)).catch(function() {});
  };
  option.onclick = function() {
   return tuneExec('--restore').then(function() { window.location.reload(); }).catch(function(e) {
    ui.addNotification(null, E('p', _('Could not restore: %s').format(e.message || e)), 'danger');
   });
  };
  option = section.taboption('carrier', form.Flag, 'roaming', _('Allow roaming'),
   _('Connect while registered on a partner network. Off by default, like the vendor setting.'));
  option.default = '0';
  // Network selection: Automatic or Manual. The mode is not stored; the UCI option `plmn` is (set = manual).
  option = section.taboption('carrier', form.ListValue, 'opmode', _('Network selection'),
   _('Automatic registers on the best network. Manual lets you search for networks and choose one; if it does not register, the modem goes back to automatic.'));
  option.value('auto', _('Automatic'));
  option.value('manual', _('Manual'));
  option.default = 'auto';
  option.cfgvalue = function(section_id) {
   try { if (window.sessionStorage.getItem('x28_opmode') === 'manual') return 'manual'; } catch (e) {}
   return this.map.data.get(this.map.config, section_id, 'plmn') ? 'manual' : 'auto';
  };
  option.write = function() {};
  option.remove = function() {};
  option = section.taboption('carrier', form.Button, 'plmnscan', _('Search networks'),
   _('Takes a few minutes and drops the data connection meanwhile; it reconnects by itself. The page reloads with the networks found.'));
  option.depends('opmode', 'manual');
  option.inputtitle = _('Scan');
  option.onclick = function() {
   var poll = function() {
    return fs.exec('/sbin/x28-plmn-scan', ['--state']).then(function(res) {
     if ((res.stdout || '').trim() !== 'running') {
      try { window.sessionStorage.setItem('x28_opmode', 'manual'); } catch (e) {}
      window.location.reload();
      return;
     }
     return new Promise(function(resolve) { window.setTimeout(resolve, 3000); }).then(poll);
    });
   };
   return fs.exec('/sbin/x28-plmn-scan', ['--start']).then(poll).catch(function(e) {
    ui.addNotification(null, E('p', _('The network search could not be started: %s').format(e.message || e)), 'danger');
   });
  };
  option = section.taboption('carrier', form.ListValue, 'plmn', _('Network'),
   _('Networks found by the last search. Search first if the list is empty.'));
  option.depends('opmode', 'manual');
  option.rmempty = false;
  option.validate = function(_section, value) {
   return /^[0-9]{5,6}$/.test(value || '') || _('Search for networks and pick one.');
  };
  option.load = function(section_id) {
   // x28-plmn-scan --last prints "plmn<TAB>name<TAB>act<TAB>status" per network (status 1 available, 2 current, 3 forbidden).
   var status = { '1': _('available'), '2': _('current'), '3': _('forbidden') };
   this.value('', _('-- search first --'));
   return fs.exec('/sbin/x28-plmn-scan', ['--last']).then(L.bind(function(res) {
    (res.stdout || '').split('\n').forEach(L.bind(function(line) {
     var f = line.split('\t');
     if (f[0]) this.value(f[0], '%s%s, %s'.format(f[0], f[1] && f[1] !== f[0] ? ' ' + f[1] : '', status[f[3]] || _('unknown')));
    }, this));
   }, this)).catch(function() {}).then(L.bind(function() {
    var cur = this.map.data.get(this.map.config, section_id, 'plmn');
    if (cur && !(cur in this.keylist.reduce(function(o, k) { o[k] = 1; return o; }, {}))) this.value(cur, cur);
    return form.Value.prototype.load.call(this, section_id);
   }, this));
  };
  // Radio technology (mipc_wan_cli nw_set_rat). SA/NSA and TDD/FDD are separate controls and not offered yet.
  option = section.taboption('carrier', form.ListValue, 'netmode', _('Network mode'),
   _('Which radio technologies the modem may use. The modem re-registers when this changes. If there is no service afterwards, set it back to Automatic: it is not undone for you.'));
  option.value('auto', _('Automatic (4G and 5G)'));
  option.value('4g', _('4G only'));
  option.value('5g', _('5G only'));
  option.default = 'auto';
  // 4G band lock (AT+EPBSE). The list is this modem's supported LTE bands.
  option = section.taboption('carrier', form.ListValue, 'lteband_mode', _('4G band lock'),
   _('Restrict which LTE bands the modem may use. The modem re-registers when this changes. If there is no service afterwards, remove the lock: it is not undone for you.'));
  option.value('none', _('No lock'));
  option.value('allow', _('Only the selected bands'));
  option.value('deny', _('All except the selected bands'));
  option.default = 'none';
  option = section.taboption('carrier', form.MultiValue, 'lteband_list', _('4G bands'));
  option.depends('lteband_mode', 'allow');
  option.depends('lteband_mode', 'deny');
  [[1, '2100 FDD'], [3, '1800 FDD'], [5, '850 FDD'], [7, '2600 FDD'], [8, '900 FDD'], [20, '800 FDD'], [28, '700 FDD'],
   [32, '1500 SDL'], [38, '2600 TDD'], [40, '2300 TDD'], [41, '2500 TDD'], [42, '3500 TDD'], [43, '3700 TDD']
  ].forEach(function(b) { option.value(String(b[0]), 'B' + b[0] + ' (' + b[1] + ' MHz)'); });
  option.rmempty = false;
  option.validate = function(_section, value) {
   return (value && value.length > 0) || _('Select at least one band.');
  };
  // 5G band lock (x28-nrband over MIPC). The list is this modem's supported NR bands.
  option = section.taboption('carrier', form.ListValue, 'nrband_mode', _('5G band lock'),
   _('Restrict which 5G (NR) bands the modem may use. 5G NSA also needs its 4G anchor band. The modem re-registers when this changes. If there is no service afterwards, remove the lock: it is not undone for you.'));
  option.value('none', _('No lock'));
  option.value('allow', _('Only the selected bands'));
  option.value('deny', _('All except the selected bands'));
  option.default = 'none';
  option.load = function(section_id) {
   return modemStatus().then(L.bind(function(st) {
    if (st.info.some(function(f) { return f[0] == 'nrband_tool' && f[1] == 'missing'; }))
     this.description = _('The band tool (x28-nrband) is not installed on this router: a 5G band lock will fail until it is. No lock is always safe.');
   }, this)).then(L.bind(form.Value.prototype.load, this, section_id));
  };
  option = section.taboption('carrier', form.MultiValue, 'nrband_list', _('5G bands'));
  option.depends('nrband_mode', 'allow');
  option.depends('nrband_mode', 'deny');
  [[1, '2100 FDD'], [3, '1800 FDD'], [5, '850 FDD'], [7, '2600 FDD'], [8, '900 FDD'], [20, '800 FDD'], [28, '700 FDD'],
   [38, '2600 TDD'], [40, '2300 TDD'], [41, '2500 TDD'], [77, '3700 TDD'], [78, '3500 TDD']
  ].forEach(function(b) { option.value(String(b[0]), 'n' + b[0] + ' (' + b[1] + ' MHz)'); });
  option.rmempty = false;
  option.validate = function(_section, value) {
   return (value && value.length > 0) || _('Select at least one band.');
  };

  // Cell lock. The mode is not stored; the UCI option `celllock` is (set = locked).
  option = section.taboption('carrier', form.ListValue, 'cellmode', _('Cell lock'),
   _('Lock the modem to one LTE cell. The modem can lock a single cell only (no list, no exclusion) and only on 4G. If the cell has no service, remove the lock: it is not removed for you.'));
  option.value('none', _('No lock'));
  option.value('lock', _('Lock to the selected cell'));
  option.default = 'none';
  option.cfgvalue = function(section_id) {
   return this.map.data.get(this.map.config, section_id, 'celllock') ? 'lock' : 'none';
  };
  option.write = function() {};
  option.remove = function() {};
  option = section.taboption('carrier', form.ListValue, 'celllock', _('Cell'),
   _('Cells the modem sees now, as EARFCN:PCI (band, signal). Reload the page to refresh the list.'));
  option.depends('cellmode', 'lock');
  option.rmempty = false;
  option.validate = function(_section, value) {
   var m = /^([0-9]{1,5}):([0-9]{1,3})$/.exec(value || '');
   return (m && +m[1] <= 46589 && +m[2] <= 511) || _('Select a cell.');
  };
  option.load = function(section_id) {
   this.value('', _('-- select a cell --'));
   return modemStatus().then(L.bind(function(st) {
    st.cells.filter(function(c) { return !c.nr; }).forEach(L.bind(function(c) {
     this.value(c.id, '%s (band %s, %s dBm)%s'.format(c.id, c.band, c.rsrp, c.serving ? ' ' + _('serving') : ''));
    }, this));
    var cur = this.map.data.get(this.map.config, section_id, 'celllock');
    if (cur && this.keylist.indexOf(cur) < 0) this.value(cur, cur);
   }, this)).then(L.bind(form.Value.prototype.load, this, section_id));
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
  option = section.taboption('advanced', form.Value, 'passthrough_mac', _('IPv4 passthrough to'),
   _('Gives this LAN device the cellular IPv4 address by DHCP, like the stock bridge mode: the X28 keeps no public IPv4 address, ' +
     'the device gets all incoming IPv4 traffic and needs its own firewall. Renew its DHCP lease after saving. Empty = off.'));
  option.datatype = 'macaddr';
  option.placeholder = _('Off');
  option.depends('iptype', '3');
  option.depends('iptype', '1');
  option.load = function(section_id) {
   return network.getHostHints().then(L.bind(function(hints) {
    hints.getMACHints().forEach(L.bind(function(h) { this.value(h[0], h[1] ? '%s (%s)'.format(h[0], h[1]) : h[0]); }, this));
   }, this)).catch(function() {}).then(L.bind(form.Value.prototype.load, this, section_id));
  };
 }
});
