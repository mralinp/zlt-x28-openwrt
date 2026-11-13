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
	load: function() { return sms(['contacts']); },

	fail: function(e) { ui.addNotification(null, E('p', e.message), 'error'); },

	rows: function(contacts) {
		var self = this;
		if (!contacts.length)
			return E('tr', { 'class': 'tr placeholder' }, E('td', { 'class': 'td', 'colspan': 3 }, E('em', _('The phone book is empty.'))));
		return contacts.slice().sort(function(a, b) { return a.name.localeCompare(b.name); }).map(function(c) {
			return E('tr', { 'class': 'tr' }, [
				E('td', { 'class': 'td', 'dir': 'auto' }, c.name),
				E('td', { 'class': 'td' }, c.number),
				E('td', { 'class': 'td right' }, [
					E('a', { 'class': 'btn cbi-button', 'href': L.url('admin/services/telephony/messages') + '?to=' + encodeURIComponent(c.number) }, _('Message')), ' ',
					E('button', { 'class': 'btn cbi-button cbi-button-remove', 'click': ui.createHandlerFn(self, function() {
						return sms(['contact-del', c.number]).then(self.refresh.bind(self)).catch(self.fail);
					}) }, _('Delete'))
				])
			]);
		});
	},

	refresh: function() {
		var self = this;
		return sms(['contacts']).then(function(contacts) { dom.content(self.body, self.rows(contacts)); });
	},

	add: function() {
		var self = this, name = this.name.value.trim(), number = this.number.value.trim();
		if (!name || !number) return;
		return sms(['contact-set', number, name]).then(function() {
			self.name.value = self.number.value = '';
			return self.refresh();
		}).catch(this.fail);
	},

	render: function(contacts) {
		this.name = E('input', { 'type': 'text', 'class': 'cbi-input-text', 'placeholder': _('Name'), 'dir': 'auto', 'maxlength': 40 });
		this.number = E('input', { 'type': 'tel', 'class': 'cbi-input-text', 'placeholder': '+989121234567' });
		this.body = E('tbody', this.rows(contacts));

		return E('div', [
			E('h2', _('Phone book')),
			E('div', { 'class': 'cbi-map-descr' }, _('Names for the numbers in Messages. Kept on the router, not on the SIM. Saving a number that is already here renames it.')),
			E('div', { 'class': 'cbi-section' }, E('table', { 'class': 'table' }, [
				E('thead', E('tr', { 'class': 'tr table-titles' }, [
					E('th', { 'class': 'th' }, _('Name')), E('th', { 'class': 'th' }, _('Number')), E('th', { 'class': 'th' })
				])),
				this.body
			])),
			E('div', { 'class': 'cbi-section' }, [
				this.name, ' ', this.number, ' ',
				E('button', { 'class': 'btn cbi-button cbi-button-add', 'click': ui.createHandlerFn(this, 'add') }, _('Add'))
			])
		]);
	},

	handleSave: null,
	handleSaveApply: null,
	handleReset: null
});
