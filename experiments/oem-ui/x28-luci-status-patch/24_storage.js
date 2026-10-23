'use strict';
'require baseclass';
'require rpc';

var callMountPoints = rpc.declare({ object: 'luci', method: 'getMountPoints' });
var targets = [
	{ mount: '/overlay', label: _('System overlay') },
	{ mount: '/data', label: _('Data') },
	{ mount: '/customer', label: _('Customer') }
];

function bytes(value) {
	return String.format('%1024.2mB', value);
}

function segment(label, value, total, color) {
	return E('div', {
		'style': 'width:' + (100 * value / total).toFixed(3) + '%;background:' + color,
		'title': label + ': ' + bytes(value)
	});
}

return baseclass.extend({
	title: _('Writable storage'),

	load: function() {
		return L.resolveDefault(callMountPoints(), {});
	},

	render: function(data) {
		var mounts = Array.isArray(data.result) ? data.result : Array.isArray(data) ? data : [];
		var table = E('div', { 'class': 'table' });

		for (var i = 0; i < targets.length; i++) {
			var mount = null;
			for (var j = 0; j < mounts.length; j++) {
				if (mounts[j].mount === targets[i].mount) {
					mount = mounts[j];
					break;
				}
			}
			if (!mount || !mount.size)
				continue;

			var size = +mount.size;
			var free = Math.max(0, +mount.free || 0);
			var available = Math.max(0, +mount.avail || 0);
			var used = Math.max(0, size - free);
			var reserved = Math.max(0, free - available);
			var description = targets[i].label + ' (' + targets[i].mount + '): ' +
				bytes(used) + ' used, ' + bytes(available) + ' available of ' + bytes(size);
			var usageBar = E('div', {
				'style': 'display:flex;height:20px;overflow:hidden;border:1px solid #bbb;border-radius:3px;background:#eee',
				'role': 'img', 'aria-label': description
			}, [
				segment(_('Used'), used, size, '#d9534f'),
				segment(_('Reserved'), reserved, size, '#999'),
				segment(_('Available'), available, size, '#5cb85c')
			]);
			table.appendChild(E('div', { 'class': 'tr' }, [
				E('div', { 'class': 'td left', 'width': '33%' }, [targets[i].label, E('small', {}, ' (' + targets[i].mount + ')')]),
				E('div', { 'class': 'td left' }, [
					usageBar,
					E('div', { 'style': 'margin-top:6px' }, bytes(used) + ' used · ' +
						bytes(reserved) + ' reserved · ' + bytes(available) +
						' available · ' + bytes(size) + ' total')
				])
			]));
		}

		return table;
	}
});
