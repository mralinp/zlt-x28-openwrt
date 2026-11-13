// SPDX-License-Identifier: GPL-2.0-only
'use strict';
'require view';
'require fs';
'require ui';
'require poll';
'require dom';

var PAGE = 10;    // conversations per page
var CHUNK = 30;   // messages shown in a conversation, and added by "Show older"

var CSS = [
	'.x28-sms{display:flex;gap:1.5em;flex-wrap:wrap;align-items:flex-start}',
	'.x28-list{flex:1 1 16em;max-width:24em;min-width:0}',
	'.x28-pane{flex:3 1 22em;min-width:0}',
	'.x28-item{padding:.5em .7em;border-radius:6px;cursor:pointer;border-bottom:1px solid rgba(128,128,128,.2)}',
	'.x28-item:hover,.x28-item:focus{background:rgba(128,128,128,.1)}',
	'.x28-item.on{background:rgba(128,128,128,.22)}',
	'.x28-item span{float:right;opacity:.65;font-size:85%;margin-left:.5em}',
	'.x28-item small{display:block;opacity:.7;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
	'.x28-pager{display:flex;justify-content:space-between;align-items:center;margin-top:.7em}',
	'.x28-head{display:flex;justify-content:space-between;align-items:center;gap:1em;flex-wrap:wrap;margin-bottom:.5em}',
	'.x28-head small{opacity:.7;margin-left:.5em}',
	'.x28-bubbles{max-height:55vh;overflow-y:auto;display:flex;flex-direction:column;gap:.45em;padding:.5em .3em}',
	'.x28-b{max-width:80%;padding:.5em .8em;border-radius:12px;white-space:pre-wrap;word-break:break-word;background:rgba(128,128,128,.16);align-self:flex-start}',
	'.x28-b.out{align-self:flex-end;background:rgba(0,120,220,.2)}',
	'.x28-b.failed{background:rgba(220,60,60,.2)}',
	'.x28-b small{display:block;opacity:.65;margin-top:.3em;white-space:normal}',
	'.x28-b small a{cursor:pointer;margin-left:.8em}',
	'.x28-compose{display:flex;gap:.5em;align-items:flex-end;margin-top:.7em}',
	'.x28-compose textarea{flex:1;min-width:0}',
	'.x28-to{display:flex;gap:.5em;flex-wrap:wrap;margin-bottom:.5em}'
].join('\n');

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

// 09121234567 and +989121234567 are one conversation: compare the last ten digits. A sender that is a name keeps the name.
function key(number) { return number.replace(/\D/g, '').slice(-10) || number; }
function dialable(number) { return /^\+?\d{3,}$/.test(number); }

function when(time, long) {
	var d = new Date(time * 1000), today = new Date().toDateString() == d.toDateString();
	var hm = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
	return long ? (today ? hm : d.toLocaleDateString() + ' ' + hm) : (today ? hm : d.toLocaleDateString());
}

// A div that behaves as a button: themes restyle real buttons too heavily for a list row.
function row(attrs, children, fn) {
	attrs.role = 'button';
	attrs.tabindex = 0;
	attrs.click = fn;
	attrs.keydown = function(ev) { if (ev.key == 'Enter' || ev.key == ' ') { ev.preventDefault(); fn(); } };
	return E('div', attrs, children);
}

return view.extend({
	load: function() {
		return Promise.all([ sms(['list']), sms(['contacts']) ]);
	},

	fail: function(e) { ui.addNotification(null, E('p', e.message), 'error'); },

	// Conversations, the one with the newest message first.
	// ponytail: the whole store is loaded and grouped in the browser; page it in x28-sms when a store grows past a few thousand messages.
	threads: function() {
		var map = {}, list = [];
		this.messages.slice().sort(function(a, b) { return a.time - b.time; }).forEach(function(m) {
			var k = key(m.number), t = map[k];
			if (!t) list.push(t = map[k] = { key: k, msgs: [] });
			t.msgs.push(m);
			t.number = m.number;
		});
		return list.sort(function(a, b) { return b.msgs[b.msgs.length - 1].time - a.msgs[a.msgs.length - 1].time; });
	},

	open: function(k) {
		this.sel = k;
		this.shown = CHUNK;
		this.draw(true);
		if (k === null) this.to.focus();
	},

	draw: function(toEnd) {
		var self = this, all = this.threads(), pages = Math.max(1, Math.ceil(all.length / PAGE));
		var t = all.filter(function(x) { return x.key === self.sel; })[0];
		if (!t) this.sel = null;   // a new message, or the conversation was deleted
		this.page = Math.min(this.page, pages - 1);

		dom.content(this.list, [
			E('button', { 'class': 'btn cbi-button cbi-button-add', 'style': 'width:100%;margin-bottom:.7em', 'click': function() { self.open(null); } }, _('New message')),
			all.length ? '' : E('p', E('em', _('No messages yet.')))
		].concat(all.slice(this.page * PAGE, (this.page + 1) * PAGE).map(function(c) {
			var last = c.msgs[c.msgs.length - 1];
			return row({ 'class': 'x28-item' + (c.key === self.sel ? ' on' : '') }, [
				E('span', when(last.time)),
				E('strong', { 'dir': 'auto' }, self.names[c.key] || c.number),
				E('small', { 'dir': 'auto' }, (last.dir == 'out' ? _('You: ') : '') + last.text)
			], function() { self.open(c.key); });
		}), pages > 1 ? E('div', { 'class': 'x28-pager' }, [
			E('button', { 'class': 'btn cbi-button', 'disabled': this.page == 0 ? '' : null, 'click': function() { self.page--; self.draw(); } }, '‹ ' + _('Newer')),
			E('span', _('Page %d of %d').format(this.page + 1, pages)),
			E('button', { 'class': 'btn cbi-button', 'disabled': this.page >= pages - 1 ? '' : null, 'click': function() { self.page++; self.draw(); } }, _('Older') + ' ›')
		]) : ''));

		// The To row, the text box and the Send button are made once, so a refresh never loses what is being typed.
		this.toRow.style.display = t ? 'none' : '';
		this.compose.style.display = t && !dialable(t.number) ? 'none' : '';
		this.thread = t;

		if (!t) {
			dom.content(this.head, E('h3', { 'style': 'margin:0' }, _('New message')));
			dom.content(this.bubbles, '');
			return;
		}
		var name = this.names[t.key], older = t.msgs.length - this.shown;
		dom.content(this.head, [
			E('h3', { 'style': 'margin:0', 'dir': 'auto' }, [ name || t.number, name ? E('small', t.number) : '' ]),
			E('button', { 'class': 'btn cbi-button cbi-button-remove', 'click': ui.createHandlerFn(this, function() {
				if (!confirm(_('Delete all %d messages of this conversation?').format(t.msgs.length))) return;
				var ids = [];
				t.msgs.forEach(function(m) { ids = ids.concat(m.ids); });
				return sms(['delete'].concat(ids)).then(self.refresh.bind(self)).catch(self.fail);
			}) }, _('Delete conversation'))
		]);
		var keep = this.bubbles.scrollHeight - this.bubbles.scrollTop;
		dom.content(this.bubbles, [
			older > 0 ? E('button', { 'class': 'btn cbi-button', 'style': 'align-self:center', 'click': function() { self.shown += CHUNK; self.draw(); } },
				_('Show older (%d more)').format(older)) : '',
			dialable(t.number) ? '' : E('em', { 'style': 'align-self:center' }, _('This sender is a name, not a number, so it cannot be answered.'))
		].concat(t.msgs.slice(-this.shown).map(function(m) {
			return E('div', { 'class': 'x28-b ' + m.dir + (m.status == 'failed' ? ' failed' : ''), 'dir': 'auto' }, [
				m.text,
				E('small', { 'dir': 'ltr' }, [
					when(m.time, true), m.status == 'failed' ? ' · ' + _('not sent') : '',
					E('a', { 'title': _('Delete this message'), 'click': function() {
						sms(['delete'].concat(m.ids)).then(self.refresh.bind(self)).catch(self.fail);
					} }, _('Delete'))
				])
			]);
		})));
		// newest at the bottom when opening or after sending; otherwise stay where the reader is
		this.bubbles.scrollTop = toEnd ? this.bubbles.scrollHeight : this.bubbles.scrollHeight - keep;
	},

	refresh: function(toEnd) {
		var self = this;
		return sms(['list']).then(function(messages) {
			var grew = messages.length > self.messages.length;
			var atEnd = self.bubbles.scrollHeight - self.bubbles.scrollTop - self.bubbles.clientHeight < 40;
			self.messages = messages;
			self.draw(toEnd === true || (grew && atEnd));
		});
	},

	send: function() {
		var self = this, to = this.thread ? this.thread.number : this.to.value.trim(), text = this.text.value;
		if (!to || !text.trim()) return;
		return sms(['send', to, text]).then(function() {
			self.text.value = '';
			self.to.value = '';
			self.pick.value = '';
		}).catch(this.fail).then(function() {
			self.sel = key(to);   // the message is kept even when it was not sent, so show its conversation
			self.page = 0;
			return self.refresh(true);
		});
	},

	render: function(data) {
		var self = this, contacts = data[1].slice().sort(function(a, b) { return a.name.localeCompare(b.name); });
		var to = new URLSearchParams(location.search).get('to') || '';
		this.messages = data[0];
		this.names = {};
		contacts.forEach(function(c) { self.names[key(c.number)] = c.name; });
		this.page = 0;
		this.shown = CHUNK;

		this.pick = E('select', { 'class': 'cbi-input-select', 'change': function() { if (self.pick.value) self.to.value = self.pick.value; } },
			[ E('option', { 'value': '' }, contacts.length ? _('Choose from the phone book…') : _('The phone book is empty')) ].concat(
				contacts.map(function(c) { return E('option', { 'value': c.number }, c.name + ' (' + c.number + ')'); })));
		this.to = E('input', { 'type': 'tel', 'class': 'cbi-input-text', 'placeholder': _('or type a number: +989121234567'), 'value': to,
			'input': function() { self.pick.value = ''; } });
		this.toRow = E('div', { 'class': 'x28-to' }, [ this.pick, this.to ]);
		this.text = E('textarea', { 'class': 'cbi-input-textarea', 'rows': 2, 'dir': 'auto', 'maxlength': 1530, 'placeholder': _('Message'),
			'keydown': function(ev) { if (ev.key == 'Enter' && (ev.ctrlKey || ev.metaKey)) self.sendButton.click(); } });
		this.sendButton = E('button', { 'class': 'btn cbi-button cbi-button-action important', 'title': _('Ctrl+Enter'), 'click': ui.createHandlerFn(this, 'send') }, _('Send'));
		this.compose = E('div', { 'class': 'x28-compose' }, [ this.text, this.sendButton ]);
		this.list = E('div', { 'class': 'x28-list' });
		this.head = E('div', { 'class': 'x28-head' });
		this.bubbles = E('div', { 'class': 'x28-bubbles' });

		// Opened from the phone book with ?to=: that person's conversation if there is one, else a new message to them.
		var all = this.threads();
		this.sel = to ? key(to) : all.length ? all[0].key : null;
		this.draw();
		// the thread is not in the page yet, so it has no height to scroll: do it once it is
		requestAnimationFrame(function() { self.bubbles.scrollTop = self.bubbles.scrollHeight; });
		poll.add(this.refresh.bind(this), 10);

		return E('div', [
			E('style', CSS),
			E('h2', _('Messages')),
			E('div', { 'class': 'cbi-map-descr' }, _('Text messages of the SIM in this router. Received messages are moved from the SIM to the router, so the SIM does not fill up.')),
			E('div', { 'class': 'cbi-section x28-sms' }, [
				this.list,
				E('div', { 'class': 'x28-pane' }, [ this.head, this.toRow, this.bubbles, this.compose ])
			])
		]);
	},

	handleSave: null,
	handleSaveApply: null,
	handleReset: null
});
