-- Copyright 2008 Steven Barth <steven@midlink.org>
-- Copyright 2011-2018 Jo-Philipp Wich <jo@mein.io>
-- Licensed to the public under the Apache License 2.0.

module("luci.controller.admin.network", package.seeall)

function index()
	local page

--	if page.inreq then
		page = entry({"admin", "network", "switch"}, view("network/switch"), _("Switch"), 20)
		page.uci_depends = { network = { ["@switch[0]"] = "switch" } }

		page = entry({"admin", "network", "wireless"}, template("vendor/wifi"), _('Wireless'), 15)
		-- Wi-Fi is owned by the vendor backend, not /etc/config/wireless.
		page.leaf = true

		page = entry({"admin", "network", "network"}, template("vendor/interfaces"), _("Interfaces"), 10)
		page.leaf   = true
		page.subindex = true

		page = node("admin", "network", "dhcp")
		page.target = template("vendor/lan")
		page.title  = _("LAN / DHCP")
		page.order  = 30

		page = node("admin", "network", "hosts")
		page.uci_depends = { dhcp = true }
		page.target = view("network/hosts")
		-- UCI hostnames do not configure the vendor DHCP service.
		page.order  = 40

		page  = node("admin", "network", "routes")
		page.target = view("network/routes")
		-- UCI routes require netifd, which is absent on this firmware.
		page.order  = 50

		entry({"admin", "network", "cellular"}, template("vendor/cellular"), _("WAN / Cellular"), 25)

		page = node("admin", "network", "diagnostics")
		page.target = view("network/diagnostics")
		page.title  = _("Diagnostics")
		page.order  = 60
--	end
end
