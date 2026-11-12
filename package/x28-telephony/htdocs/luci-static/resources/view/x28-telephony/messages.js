// SPDX-License-Identifier: GPL-2.0-only
'use strict';
'require view';
'require fs';
'require ui';
'require poll';
'require dom';

// The backend prints JSON; a failure is {"error": ...} with a non-zero exit code.
function sms(args) {
	return fs.exec('/usr/sbin/x28-sms', args).then(function(res) {
		var out = null;
		try { out = JSON.parse(res.stdout); } catch (e) {}
		if (res.code !== 0 || out === null)
			throw new Error(out && out.error || res.stderr || _('The command failed'));
		return out;
	});
}

// 09121234567 and +989121234567 are one person: compare the last ten digits.
function tail(number) { return number.replace(/\D/g, '').slice(-10); }

return view.extend({
	load: function() {
		return Promise.all([ sms(['list']), sms(['contacts']) ]);
	},

	rows: function(messages) {
		var names = this.names, self = this;
		if (!messages.length)
			return E('tr', { 'class': 'tr placeholder' }, E('td', { 'class': 'td', 'colspan': 4 }, E('em', _('No messages yet.'))));
		return messages.slice().reverse().map(function(m) {
			var who = names[tail(m.number)];
			return E('tr', { 'class': 'tr' }, [
				E('td', { 'class': 'td', 'style': 'white-space:nowrap' }, new Date(m.time * 1000).toLocaleString()),
				E('td', { 'class': 'td', 'style': 'white-space:nowrap' }, [
					m.dir == 'out' ? '→ ' : '← ', who ? who + ' (' + m.number + ')' : m.number,
					m.status == 'failed' ? E('span', { 'class': 'label warning', 'style': 'margin-left:.5em' }, _('not sent')) : ''
				]),
				E('td', { 'class': 'td', 'style': 'white-space:pre-wrap;word-break:break-word', 'dir': 'auto' }, m.text),
				E('td', { 'class': 'td right' }, [
					m.dir == 'in' ? E('button', { 'class': 'btn cbi-button', 'click': function() {
						self.to.value = m.number; self.text.focus();
					} }, _('Reply')) : '', ' ',
					E('button', { 'class': 'btn cbi-button cbi-button-remove', 'click': ui.createHandlerFn(self, function() {
						return sms(['delete'].concat(m.ids)).then(self.refresh.bind(self)).catch(self.fail);
					}) }, _('Delete'))
				])
			]);
		});
	},

	fail: function(e) { ui.addNotification(null, E('p', e.message), 'error'); },

	refresh: function() {
		var self = this;
		return sms(['list']).then(function(messages) { dom.content(self.body, self.rows(messages)); });
	},

	send: function() {
		var self = this, to = this.to.value.trim(), text = this.text.value;
		if (!to || !text) return;
		return sms(['send', to, text]).then(function() {
			self.text.value = '';
			ui.addNotification(null, E('p', _('Message sent to %s.').format(to)), 'info');
		}).catch(this.fail).then(this.refresh.bind(this));
	},

	render: function(data) {
		var self = this, contacts = data[1];
		this.names = {};
		contacts.forEach(function(c) { self.names[tail(c.number)] = c.name; });
		this.to = E('input', { 'type': 'tel', 'class': 'cbi-input-text', 'list': 'x28-contacts', 'placeholder': '+989121234567',
			'value': new URLSearchParams(location.search).get('to') || '' });
		this.text = E('textarea', { 'class': 'cbi-input-textarea', 'rows': 3, 'style': 'width:100%', 'dir': 'auto', 'maxlength': 1530 });
		this.body = E('tbody', this.rows(data[0]));
		poll.add(this.refresh.bind(this), 10);

		return E('div', [
			E('h2', _('Messages')),
			E('div', { 'class': 'cbi-map-descr' }, _('Text messages of the SIM in this router. Received messages are moved from the SIM to the router, so the SIM does not fill up.')),
			E('div', { 'class': 'cbi-section' }, [
				E('h3', _('New message')),
				E('datalist', { 'id': 'x28-contacts' }, contacts.map(function(c) { return E('option', { 'value': c.number }, c.name); })),
				E('div', { 'class': 'cbi-value' }, [ E('label', { 'class': 'cbi-value-title' }, _('To')), E('div', { 'class': 'cbi-value-field' }, this.to) ]),
				E('div', { 'class': 'cbi-value' }, [ E('label', { 'class': 'cbi-value-title' }, _('Text')), E('div', { 'class': 'cbi-value-field' }, this.text) ]),
				E('div', { 'class': 'right' }, E('button', { 'class': 'btn cbi-button cbi-button-action important', 'click': ui.createHandlerFn(this, 'send') }, _('Send')))
			]),
			E('div', { 'class': 'cbi-section' }, E('table', { 'class': 'table' }, [
				E('thead', E('tr', { 'class': 'tr table-titles' }, [
					E('th', { 'class': 'th' }, _('Time')), E('th', { 'class': 'th' }, _('From / to')), E('th', { 'class': 'th' }, _('Text')), E('th', { 'class': 'th' })
				])),
				this.body
			]))
		]);
	},

	handleSave: null,
	handleSaveApply: null,
	handleReset: null
});
