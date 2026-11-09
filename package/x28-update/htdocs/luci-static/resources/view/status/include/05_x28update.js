'use strict';
'require baseclass';
'require fs';
'require ui';

// Status > Overview: a notice when a newer signed X28 image is released (#511), and "Upgrade now" (#515), which runs x28-upgrade in
// the background. The overview polls its includes; one check per page load is enough, and the script caches its answer in /tmp.
var check;
var LOG = '/tmp/x28-upgrade.log';

function follow() {
	return fs.read(LOG).catch(function() { return ''; }).then(function(text) {
		var lines = text.trim().split('\n'), last = lines[lines.length - 1];
		if (/FAILED/.test(text)) {
			ui.showModal(_('Upgrade refused'), [
				E('pre', {}, text),
				E('div', { 'class': 'right' }, E('button', { 'class': 'btn', 'click': ui.hideModal }, _('Close')))
			]);
		}
		else if (/up to date/.test(text)) {
			ui.hideModal();
			ui.addNotification(null, E('p', {}, _('Already up to date.')));
		}
		else if (/flashing/.test(text)) {
			ui.showModal(_('Flashing…'), [ E('p', { 'class': 'spinning' }, last) ]);
			ui.awaitReconnect();
		}
		else {
			ui.showModal(_('Upgrading…'), [ E('p', { 'class': 'spinning' }, last || _('Starting…')) ]);
			return new Promise(function(r) { window.setTimeout(r, 2000); }).then(follow);
		}
	});
}

function upgrade(u) {
	ui.showModal(_('Upgrade to %s?').format(u.latest), [
		E('p', {}, _('The signed image %s is downloaded, checked and written to the other A/B slot, which then boots. The unit reboots and is offline for a few minutes; the running slot stays as the fall-back. Settings are not kept.').format(u.latest)),
		E('div', { 'class': 'right' }, [
			E('button', { 'class': 'btn', 'click': ui.hideModal }, _('Cancel')), ' ',
			E('button', { 'class': 'btn cbi-button-action important', 'click': function() {
				return fs.exec('/usr/sbin/x28-upgrade', [ '-y', '-b' ]).then(follow).catch(function(e) {
					ui.addNotification(null, E('p', {}, _('Could not start the upgrade: %s').format(e.message)));
					ui.hideModal();
				});
			} }, _('Upgrade now'))
		])
	]);
}

return baseclass.extend({
	title: _('Firmware update'),

	load: function() {
		if (!check)
			check = L.resolveDefault(fs.exec('/usr/libexec/x28-update-check'), {}).then(function(res) {
				try { return JSON.parse(res.stdout); } catch (e) { return null; }
			});
		return check;
	},

	render: function(u) {
		if (!u || !u.newer)
			return null;  // the section stays hidden
		return E('p', {}, [
			_('A newer X28 image is released: %s (running %s).').format(u.latest, u.current || _('unknown')), ' ',
			E('a', { href: u.page, target: '_blank', rel: 'noreferrer' }, _('Release notes')), ' | ',
			E('a', { href: u.url, rel: 'noreferrer' }, _('Signed sysupgrade image')), ' ',
			E('button', { 'class': 'btn cbi-button-action', 'click': function() { upgrade(u); } }, _('Upgrade now…'))
		]);
	}
});
