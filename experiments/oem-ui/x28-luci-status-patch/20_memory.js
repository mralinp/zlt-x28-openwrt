'use strict';
'require baseclass';
'require rpc';

var callSystemInfo = rpc.declare({ object: 'system', method: 'info' });
var colors = {
	used: '#d9534f', cached: '#5bc0de', buffered: '#f0ad4e', free: '#5cb85c'
};

function bytes(value) {
	return String.format('%1024.2mB', value);
}

function segment(label, value, total, color) {
	return E('div', {
		'style': 'width:' + (100 * value / total).toFixed(3) + '%;background:' + color,
		'title': label + ': ' + bytes(value)
	});
}

function bar(parts, total, description) {
	return E('div', {
		'style': 'display:flex;height:20px;overflow:hidden;border:1px solid #bbb;border-radius:3px;background:#eee',
		'role': 'img',
		'aria-label': description
	}, parts.map(function(part) {
		return segment(part.label, part.value, total, part.color);
	}));
}

function legend(parts) {
	return E('div', { 'style': 'display:flex;flex-wrap:wrap;gap:4px 14px;margin-top:6px' },
		parts.map(function(part) {
			return E('span', {}, [
				E('span', { 'style': 'display:inline-block;width:10px;height:10px;margin-right:4px;background:' + part.color }),
				part.label + ': ' + bytes(part.value)
			]);
		}));
}

function row(label, content) {
	return E('div', { 'class': 'tr' }, [
		E('div', { 'class': 'td left', 'width': '33%' }, label),
		E('div', { 'class': 'td left' }, content)
	]);
}

return baseclass.extend({
	title: _('Memory'),

	load: function() {
		return L.resolveDefault(callSystemInfo(), {});
	},

	render: function(systeminfo) {
		var mem = L.isObject(systeminfo.memory) ? systeminfo.memory : {};
		var swap = L.isObject(systeminfo.swap) ? systeminfo.swap : {};
		var table = E('div', { 'class': 'table' });
		var total = +mem.total || 0;

		if (total > 0) {
			var free = Math.max(0, +mem.free || 0);
			var cached = Math.max(0, +mem.cached || 0);
			var buffered = Math.max(0, +mem.buffered || 0);
			var used = Math.max(0, total - free - cached - buffered);
			var parts = [
				{ label: _('Used'), value: used, color: colors.used },
				{ label: _('Cached'), value: cached, color: colors.cached },
				{ label: _('Buffered'), value: buffered, color: colors.buffered },
				{ label: _('Free'), value: free, color: colors.free }
			];
			var content = [
				E('div', { 'style': 'margin-bottom:5px' }, bytes(total) + ' total'),
				bar(parts, total, _('RAM usage') + ': ' + parts.map(function(p) { return p.label + ' ' + bytes(p.value); }).join(', ')),
				legend(parts)
			];

			if (mem.available != null)
				content.push(E('div', { 'style': 'margin-top:6px;color:#555' },
					_('Available to apps (kernel estimate)') + ': ' + bytes(mem.available)));

			table.appendChild(row(_('RAM'), content));
		}

		if (swap.total > 0) {
			var swapUsed = Math.max(0, swap.total - swap.free);
			var swapParts = [ { label: _('Used'), value: swapUsed, color: colors.used } ];
			var swapPercent = Math.floor(100 * swapUsed / swap.total);
			table.appendChild(row(_('Swap'), [
				E('div', { 'style': 'margin-bottom:5px' }, bytes(swap.total) + ' total'),
				bar(swapParts, swap.total, _('Swap usage') + ': ' + bytes(swapUsed) + ' used of ' + bytes(swap.total)),
				E('div', { 'style': 'margin-top:6px' }, bytes(swapUsed) + ' used · ' +
					bytes(Math.max(0, swap.free)) + ' remaining · ' + swapPercent + '% used')
			]));
		}

		return table;
	}
});
