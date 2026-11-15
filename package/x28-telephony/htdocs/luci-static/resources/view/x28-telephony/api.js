// SPDX-License-Identifier: GPL-2.0-only
'use strict';
'require view';
'require fs';
'require ui';
'require dom';

function sms(args) {
	return fs.exec('/usr/sbin/x28-sms', args).then(function(res) {
		var out = null;
		try { out = JSON.parse(res.stdout); } catch (e) {}
		if (res.code !== 0 || out === null)
			throw new Error(out && out.error || res.stderr || _('The command failed'));
		return out;
	});
}

return view.extend({
	load: function() { return Promise.all([ sms(['keys']), sms(['webhook']) ]); },

	fail: function(e) { ui.addNotification(null, E('p', e.message), 'error'); },

	rows: function(keys) {
		var self = this;
		if (!keys.length)
			return E('tr', { 'class': 'tr placeholder' }, E('td', { 'class': 'td', 'colspan': 3 }, E('em', _('No API keys. Without one the API answers nobody.'))));
		return keys.map(function(k) {
			return E('tr', { 'class': 'tr' }, [
				E('td', { 'class': 'td' }, k.label),
				E('td', { 'class': 'td' }, new Date(k.created * 1000).toLocaleString()),
				E('td', { 'class': 'td right' }, E('button', { 'class': 'btn cbi-button cbi-button-remove', 'click': ui.createHandlerFn(self, function() {
					return sms(['key-del', k.id]).then(self.refresh.bind(self)).catch(self.fail);
				}) }, _('Revoke')))
			]);
		});
	},

	refresh: function() {
		var self = this;
		return sms(['keys']).then(function(keys) { dom.content(self.body, self.rows(keys)); });
	},

	create: function() {
		var self = this, label = this.label.value.trim();
		if (!label) return;
		return sms(['key-add', label]).then(function(res) {
			self.label.value = '';
			ui.showModal(_('New API key'), [
				E('p', _('Copy it now. Only a hash is kept, so it cannot be shown again.')),
				E('pre', { 'style': 'user-select:all;word-break:break-all;white-space:pre-wrap' }, res.key),
				E('div', { 'class': 'right' }, E('button', { 'class': 'btn cbi-button', 'click': ui.hideModal }, _('Close')))
			]);
			return self.refresh();
		}).catch(this.fail);
	},

	saveHook: function() {
		return sms(['webhook', this.hook.value.trim()]).then(function() {
			ui.addNotification(null, E('p', _('Saved.')), 'info');
		}).catch(this.fail);
	},

	render: function(data) {
		var base = location.origin + '/cgi-bin/x28-telephony/messages';
		this.label = E('input', { 'type': 'text', 'class': 'cbi-input-text', 'placeholder': _('Used by (for example: home assistant)'), 'maxlength': 40 });
		this.hook = E('input', { 'type': 'url', 'class': 'cbi-input-text', 'style': 'width:30em;max-width:100%', 'placeholder': 'http://192.168.70.10:8080/sms', 'value': data[1].url });
		this.body = E('tbody', this.rows(data[0]));

		return E('div', [
			E('h2', _('API')),
			E('div', { 'class': 'cbi-map-descr' }, _('Other machines on your network can read and send text messages with an API key. At most 30 messages are sent per hour.')),
			E('div', { 'class': 'cbi-section' }, [
				E('h3', _('API keys')),
				E('table', { 'class': 'table' }, [
					E('thead', E('tr', { 'class': 'tr table-titles' }, [
						E('th', { 'class': 'th' }, _('Name')), E('th', { 'class': 'th' }, _('Created')), E('th', { 'class': 'th' })
					])),
					this.body
				]),
				E('p', [ this.label, ' ', E('button', { 'class': 'btn cbi-button cbi-button-add', 'click': ui.createHandlerFn(this, 'create') }, _('Create key')) ])
			]),
			E('div', { 'class': 'cbi-section' }, [
				E('h3', _('Received messages')),
				E('p', _('Each received message is sent as JSON to this address (HTTP POST). Leave it empty to turn this off.')),
				E('p', [ this.hook, ' ', E('button', { 'class': 'btn cbi-button cbi-button-save', 'click': ui.createHandlerFn(this, 'saveHook') }, _('Save')) ])
			]),
			E('div', { 'class': 'cbi-section' }, [
				E('h3', _('Usage')),
				E('p', _('The router\'s certificate is self-signed, hence -k.')),
				E('pre', { 'style': 'white-space:pre-wrap;word-break:break-all' }, [
					'# ' + _('read all messages') + '\n',
					'curl -k -H "Authorization: Bearer $KEY" ' + base + '\n\n',
					'# ' + _('send one') + '\n',
					'curl -k -H "Authorization: Bearer $KEY" --data-urlencode to=+989121234567 --data-urlencode "text=Hello" ' + base + '\n',
					'curl -k -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d \'{"to":"+989121234567","text":"Hello"}\' ' + base + '\n'
				])
			])
		]);
	},

	handleSave: null,
	handleSaveApply: null,
	handleReset: null
});
