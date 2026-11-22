#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# x28-switch apply guard against a fake swconfig and uci: the stock table loads, an edited sane table (also named
# sections) loads, tables whose LAN VLAN has no tagged CPU port are refused before load, a wrong chip is refused, and a
# read-back that differs is flagged.
d=$(mktemp -d); trap 'rm -rf "$d"' EXIT
bin=$d/bin; mkdir "$bin"
# table file: lines "<section> <vlan> <ports>"
cat > "$bin/swconfig" <<'S'
#!/bin/sh
[ "$1" = list ] && { echo "Found: ${CHIP:-switch0 - MT7531AE}"; exit 0; }
echo "$@" >> "$LOG"
[ "$5" = get ] && { awk -v v="$4" '$2==v { $1=$2=""; print }' "${SHOWN:-$TABLE}"; exit 0; }
exit 0
S
cat > "$bin/uci" <<'S'
#!/bin/sh
[ "$1" = -q ] && shift
case $1 in
show) awk '{ print "network." $1 "=switch_vlan" }' "$TABLE" ;;
get) s=${2#network.}; s=${s%.*}; o=${2##*.}
	awk -v s="$s" -v o="$o" '$1==s { if (o=="vlan") print $2; else { $1=$2=""; print } }' "$TABLE" ;;
esac
S
chmod +x "$bin"/*
export PATH=$bin:$PATH LOG=$d/log TABLE=$d/table
. "$(dirname "$0")/../package/x28-switch/files/switch.sh"
run() { : > "$LOG"; setup_switch 2>"$d/err"; }
t() { : > "$TABLE"; unset SHOWN; for r in "$@"; do echo "$r" >> "$TABLE"; done; }

t '@switch_vlan[0] 1 1 5t' '@switch_vlan[1] 2 2 5t' '@switch_vlan[2] 3 4 5t' '@switch_vlan[3] 4 0 6t'
run && grep -q 'load network' "$LOG" && [ ! -e /tmp/x28-switch.failed ] || { cat "$d/err"; echo "stock table must load"; exit 1; }
t 'lan 1 1 2 5t' 'wan 2 4 0 6t'
run || { echo "edited and named sections must load"; exit 1; }
t '@switch_vlan[0] 1 1 2 4' '@switch_vlan[1] 2 5t'
! run && ! grep -q load "$LOG" && [ -e /tmp/x28-switch.failed ] || { echo "LAN and CPU in different VLANs must be refused"; exit 1; }
t '@switch_vlan[0] 1 1 5t' '@switch_vlan[1] 2 2'
! run && ! grep -q load "$LOG" || { echo "a LAN VLAN without CPU must be refused"; exit 1; }
t '@switch_vlan[0] 1 1t 2'
! run && ! grep -q load "$LOG" || { echo "1t is not a CPU port"; exit 1; }
t '@switch_vlan[0] 1 5t 6t'
! run && ! grep -q load "$LOG" || { echo "no LAN socket must be refused"; exit 1; }
t '@switch_vlan[0] 1 1 5t'; export CHIP='switch0 - OTHER'
! run && ! grep -q load "$LOG" || { echo "wrong chip must be refused"; exit 1; }
unset CHIP
t '@switch_vlan[0] 1 1 5t'; printf '@switch_vlan[0] 1 2 5t\n' > "$d/shown"; export SHOWN=$d/shown
! run && [ -e /tmp/x28-switch.failed ] || { echo "drifted read-back must be flagged"; exit 1; }
rm -f /tmp/x28-switch.failed
echo ok
