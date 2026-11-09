'use strict';
'require baseclass';
'require fs';

// Status > Overview: a notice when a newer signed X28 image is released (#511). The overview polls its includes; one check per
// page load is enough, and the script caches its answer in /tmp.
var check;

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
			E('a', { href: u.url, rel: 'noreferrer' }, _('Signed sysupgrade image')), '. ',
			_('Flash it under System > Backup / Flash Firmware.')
		]);
	}
});
