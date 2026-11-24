#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# x28-bearer-watch against a fake modem and event listener (#662): an announced end exits at once, whatever a query
# says; without announcements, two answered queries without the call; failed queries and unseen calls never exit.
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
S=$(dirname "$0")/../package/x28-mipc/files/x28-bearer-watch
fail() { echo "FAIL: $*"; exit 1; }
# One plan line per round, "<listener exit> <query answer>": 0 = announced, 124 = nothing announced, 1 = no listener;
# up, gone, other or err. An empty plan ends the loop (listener unavailable, then sleep fails).
cat > "$t/ev" <<'X'
#!/bin/sh
[ "$1 $2 $3" = "dcwait 4 60" ] || { echo "bad args: $*" >> "$T/bad"; exit 2; }
l=$(head -n 1 "$T/plan"); [ -n "$l" ] || { : > "$T/over"; exit 1; }
[ "$l" != hang ] || { echo $$ > "$T/evpid"; exec /bin/sleep 30; }
sed -i.bak 1d "$T/plan"; echo "${l#* }" > "$T/now"; exit "${l%% *}"
X
printf '#!/bin/sh\n[ ! -e "$T/over" ]\n' > "$t/sleep"
cat > "$t/mipc_wan_cli" <<'X'
#!/bin/sh
case "$(cat "$T/now")" in
	up) echo '{ "CID": 4, "v4_addr": "5.201.184.167", "iface": "ccmni1", "apn_type": 1 }' ;;
	other) echo '{ "CID": 1, "iface": "ccmni2" }' ;;
	gone) echo ;;
	err) exit 1 ;;
esac
X
printf '#!/bin/sh\nshift; exec "$@"\n' > "$t/timeout"; printf '#!/bin/sh\n' > "$t/logger"
chmod +x "$t"/*
export T="$t" X28_BW_EVENT="$t/ev"
run() { rm -f "$t/over"; printf '%s\n' "$@" > "$t/plan"; PATH="$t:$PATH" sh "$S" ccmni1 4; }
left() { [ "$(grep -c . "$t/plan")" = "$1" ] || fail "$2"; }
run '124 up' '124 up' '124 up'; [ $? = 0 ] || fail 'exited with the bearer present'
run '124 up' '0 up' '124 up'; [ $? = 1 ] || fail 'an announced end did not exit (the modem may list a re-created call)'
left 1 'did not exit at the announcement'
run '124 gone' '124 gone' '124 up'; [ $? = 0 ] || fail 'polling reconnected for a call it never saw'
run '124 up' '124 gone' '124 gone' '124 up'; [ $? = 1 ] || fail 'unannounced loss not caught by polling'
left 1 'polling did not exit at the second miss'
run '124 up' '124 gone' '124 up' '124 gone' '124 up'; [ $? = 0 ] || fail 'non-consecutive misses made it exit'
run '124 up' '124 gone' '124 err' '124 gone'; [ $? = 1 ] || fail 'a failed query between misses reset the count'
run '1 up' '1 gone' '1 gone' '1 up'; [ $? = 1 ] || fail 'without a listener, polling did not take over'
run '124 up' '124 other' '124 other'; [ $? = 1 ] || fail 'a bearer on another ccmni hid the loss'
# netifd's TERM takes the listener down too (it holds a modem port).
printf 'hang\n' > "$t/plan"; PATH="$t:$PATH" sh "$S" ccmni1 4 & w=$!
i=0; while [ ! -s "$t/evpid" ] && [ $i -lt 50 ]; do /bin/sleep 0.1; i=$((i + 1)); done
kill -TERM $w; wait $w; /bin/sleep 0.2
! kill -0 "$(cat "$t/evpid")" 2>/dev/null || fail 'the listener outlived the watcher'
[ ! -e "$t/bad" ] || fail "listener called wrong: $(cat "$t/bad")"
PATH="$t:$PATH" sh "$S" 'x;reboot' 4; [ $? = 2 ] || fail 'accepted a bad device name'
PATH="$t:$PATH" sh "$S" ccmni1 '4;x'; [ $? = 2 ] || fail 'accepted a bad call id'
echo 'PASS: bearer watch exits on an announced end or two answered misses only'
