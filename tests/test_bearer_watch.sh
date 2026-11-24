#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# x28-bearer-watch against a fake modem: exits only after two answered queries without the bearer (#662).
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
S=$(dirname "$0")/../package/x28-mipc/files/x28-bearer-watch
fail() { echo "FAIL: $*"; exit 1; }
# Each sleep takes the next answer from $t/plan (one per poll): up, gone or err; an empty plan ends the loop.
cat > "$t/sleep" <<'X'
#!/bin/sh
n=$(head -n 1 "$T/plan"); [ -n "$n" ] || exit 1
sed -i.bak 1d "$T/plan"; echo "$n" > "$T/now"
X
cat > "$t/mipc_wan_cli" <<'X'
#!/bin/sh
case "$(cat "$T/now")" in
	up) echo '{ "CID": 0, "v4_addr": "5.201.184.167", "iface": "ccmni1", "apn_type": 1 }' ;;
	other) echo '{ "CID": 1, "iface": "ccmni2" }' ;;
	gone) echo ;;
	err) exit 1 ;;
esac
X
printf '#!/bin/sh\nshift; exec "$@"\n' > "$t/timeout"; printf '#!/bin/sh\n' > "$t/logger"
chmod +x "$t"/*
export T="$t"
run() { printf '%s\n' "$@" > "$t/plan"; PATH="$t:$PATH" sh "$S" ccmni1; }
run up up up; [ $? = 0 ] || fail 'exited with the bearer present'
run up gone gone up; [ $? = 1 ] || fail 'kept running after the bearer was gone twice'
[ "$(cat "$t/plan")" = up ] || fail 'did not exit at the second miss'
run up gone up gone up gone; [ $? = 0 ] || fail 'non-consecutive misses made it exit'
run err err err err; [ $? = 0 ] || fail 'a failed query counted as a lost bearer'
run up gone err gone; [ $? = 1 ] || fail 'a failed query between misses reset the count'
run up other other; [ $? = 1 ] || fail 'a bearer on another ccmni hid the loss'
run gone gone other other gone; [ $? = 0 ] || fail 'reconnected for a call it never saw'
PATH="$t:$PATH" sh "$S" 'x;reboot'; [ $? = 2 ] || fail 'accepted a bad device name'
echo 'PASS: bearer watch exits on two answered misses only'
