'use strict';
'require baseclass';
'require fs';

var sensors = [
	{ label: _('SoC'), path: '/sys/class/thermal/thermal_zone0/temp' },
	{ label: _('5G modem'), path: '/sys/class/thermal/thermal_zone9/temp' },
	{ label: _('PMIC'), path: '/sys/class/thermal/thermal_zone16/temp' }
];

return baseclass.extend({
	title: _('Temperatures'),

	load: function() {
		return Promise.all(sensors.map(function(sensor) {
			return L.resolveDefault(fs.read(sensor.path), null);
		}));
	},

	render: function(values) {
		var table = E('div', { 'class': 'table' });

		for (var i = 0; i < sensors.length; i++) {
			var millidegrees = parseInt(values[i], 10);
			var temperature = Number.isFinite(millidegrees) &&
				millidegrees > -40000 && millidegrees < 130000
				? (millidegrees / 1000).toFixed(1) + ' °C'
				: '?';

			table.appendChild(E('div', { 'class': 'tr' }, [
				E('div', { 'class': 'td left', 'width': '33%' }, sensors[i].label),
				E('div', { 'class': 'td left' }, temperature)
			]));
		}

		return table;
	}
});
