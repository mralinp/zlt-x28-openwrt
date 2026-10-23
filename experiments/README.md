# Experiments and historical UI work

`oem-ui/` preserves original UI changes from the live OEM system. These are excluded from the native firmware image. The existing root `router/` deployment tree predates this migration; it is not synchronized automatically with these historical bundles.

`stock-luci-preview/` is an unfinished attempt to use genuine installed stock LuCI views through a separate read-only gateway. It is not a functional or validated native backend and must not be installed automatically.
