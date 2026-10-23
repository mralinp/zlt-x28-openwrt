# ZLT X28 LuCI Status patch

Applied to the live firmware 1.5.13 router on 2026-10-20. This changes only LuCI Status display and adds read-only permission for three thermal sysfs files. It does not tune or reduce actual RAM use.

- `20_memory.js`: displays one RAM bar with **used, cached, buffered, and free** as disjoint segments that sum to total. It also shows the kernel's `MemAvailable` estimate separately, since that estimate overlaps with reclaimable cache. Swap has a **used-only** bar, so 0% is empty and 100% means full.
- `24_storage.js`: displays `/overlay`, `/data`, and `/customer` writable volumes, with used, filesystem-reserved, and available space. It excludes firmware and modem partitions, which are not general file storage.
- `25_temperature.js`: shows SoC, 5G modem, and PMIC temperatures from thermal zones 0, 9, and 16. It omits other zones, including one invalid negative GPS sensor.
- `x28-temperature.json`: read-only LuCI RPC ACL for those three sensor files.
- `20_memory.original.js`: original OEM LuCI memory widget for rollback.

Installed paths:

```text
/www/luci-static/resources/view/status/include/20_memory.js
/www/luci-static/resources/view/status/include/24_storage.js
/www/luci-static/resources/view/status/include/25_temperature.js
/usr/share/rpcd/acl.d/x28-temperature.json
```

To roll back over the existing root SSH connection, copy `20_memory.original.js` to `/tmp/20_memory.js` on the router, then run:

```sh
cp /tmp/20_memory.js /www/luci-static/resources/view/status/include/20_memory.js
rm /www/luci-static/resources/view/status/include/25_temperature.js
rm /www/luci-static/resources/view/status/include/24_storage.js
rm /usr/share/rpcd/acl.d/x28-temperature.json
/etc/init.d/rpcd restart
```

Reload LuCI after rollback. The rollback affects only the status page and rpcd permissions. Firmware updates or factory reset may remove this overlay patch.

Verification performed: JavaScript syntax and JSON parsing, live LuCI Overview showing the RAM/swap/storage bars and all three temperatures, and outbound ping after the first deployment. These display changes do not alter actual memory, swap, or storage use.
