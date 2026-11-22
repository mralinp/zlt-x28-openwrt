#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# x28-switch apply guard against a fake swconfig and uci: the stock table loads, a table with no tagged CPU port or no
# untagged LAN port is refused, a wrong chip is refused, and a changed (but sane) table is no longer an error.
d=$(mktemp -d); trap 'rm -rf "$d"' EXIT
bin=$d/bin; mkdir "$bin"
cat > "$bin/swconfig" <<'S'
#!/bin/sh
[ "$1" = list ] && { echo "Found: ${CHIP:-switch0 - MT7531AE}"; exit 0; }
echo "$@" >> "$LOG"
S
cat > "$bin/uci" <<'S'
#!/bin/sh
cat "$TABLE"
S
chmod +x "$bin"/*
export PATH=$bin:$PATH LOG=$d/log TABLE=$d/table
. "$(dirname "$0")/../package/x28-switch/files/switch.sh"
run() { : > "$LOG"; setup_switch 2>/dev/null; }
vl() { printf "network.@switch_vlan[%s].ports='%s'\n" "$@" >> "$TABLE"; }

: > "$TABLE"; vl 0 '1 5t'; vl 1 '2 5t'; vl 2 '4 5t'; vl 3 '0 6t'
run && grep -q 'load network' "$LOG" && [ ! -e /tmp/x28-switch.failed ] || { echo "stock table must load"; exit 1; }
: > "$TABLE"; vl 0 '1 2 5t'; vl 1 '4 0 6t'; vl 2 '3'   # a deliberate change
run && grep -q 'load network' "$LOG" || { echo "changed sane table must load"; exit 1; }
: > "$TABLE"; vl 0 '1 2 4'; vl 1 '0'                   # no tagged CPU port
! run && [ ! -s "$LOG" ] && [ -e /tmp/x28-switch.failed ] || { echo "no CPU port must be refused"; exit 1; }
: > "$TABLE"; vl 0 '5t 6t'                             # no LAN port
! run && [ ! -s "$LOG" ] || { echo "no LAN port must be refused"; exit 1; }
: > "$TABLE"; vl 0 '1 5t'
export CHIP='switch0 - OTHER'; ! run && [ ! -s "$LOG" ] || { echo "wrong chip must be refused"; exit 1; }
unset CHIP; rm -f /tmp/x28-switch.failed
echo ok
