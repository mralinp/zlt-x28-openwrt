#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# package/x28-telephony's x28-sms against a fake modem (a script standing in for `mipc_wan_cli --at_cmd`); no device.
# Needs lua (5.1) and flock.
set -e
dir=$(mktemp -d); trap 'rm -rf "$dir"' EXIT
sms=${X28_SMS_BIN:-$(dirname "$0")/../package/x28-telephony/files/x28-sms}
export X28_SMS_DIR=$dir/store X28_SMS_AT=$dir/at
run() { lua "$sms" "$@"; }

run selftest >/dev/null

mkdir "$dir/sim"
cat > "$dir/at" <<AT
#!/bin/sh
echo "\$1" >> $dir/at.log
case "\$1" in
AT+CPMS?) n=\$(ls $dir/sim | wc -l); echo "+CPMS: \"SM\", \$n, 50, \"SM\", \$n, 50, \"SM\", \$n, 50"; echo OK ;;
AT+CMGR=*) echo 'stop log print.'; echo 'AT response:'; echo; cat $dir/sim/\${1#*=} 2>/dev/null && echo && echo OK || echo '+CME ERROR: 321' ;;
AT+CMGD=*) rm $dir/sim/\${1#*=}; echo OK ;;
AT+CMGS=*) if [ -e $dir/nosend ]; then echo ERROR; else echo '+CMGS: 5'; echo OK; fi ;;
*) echo OK ;;
esac
AT
chmod +x "$dir/at"
# slot 3: a plain message; 4 and 5: a two-part one, second part first; 7: a sent draft; 8: not a PDU. Only 3, 4, 5 may go.
slot() { printf '+CMGR: %s,, 24\n%s\n' "$2" "$3" > "$dir/sim/$1"; }
slot 3 0 07911326040000F0040B911346610089F60000208062917314080CC8F71D14969741F977FD07
slot 4 1 00440C918939210000000008421121000000000A0500032A020206270645
slot 5 0 00440C918939210000000008421121000000000A0500032A020106330644
slot 7 3 0001000B916407281553F800000AE8329BFD4697D9EC37
slot 8 0 ZZ

run poll | grep -q '"new":3'
out=$(run list)
echo "$out" | grep -q '"number":"+31641600986".*"text":"How are you?"'
echo "$out" | grep -q '"complete":true,"dir":"in","ids":\["[0-9a-f]*","[0-9a-f]*"\],"number":"+989312000000".*"text":"سلام"'
for i in 3 4 5; do grep -qx "AT+CMGD=$i" "$dir/at.log"; done
if grep -q 'CMGD=[78]' "$dir/at.log"; then exit 1; fi
[ "$(ls "$dir/sim" | tr '\n' ' ')" = '7 8 ' ]
# nothing new: the two that stay are not read again
n=$(grep -c CMGR "$dir/at.log"); run poll | grep -q '"new":0'; [ "$(grep -c CMGR "$dir/at.log")" = "$n" ]

# sending: the PDU goes out, the message is kept; a refused one is kept as failed
run send +46708251358 hellohello | grep -q '"ok":true'
grep -qx 'AT+CMGS=22,"0001000B916407281553F800000AE8329BFD4697D9EC37"' "$dir/at.log"
run list | grep -q '"dir":"out".*"status":"sent","text":"hellohello"'
for bad in 12 +12ab '+1;reboot' ''; do if run send "$bad" hi >/dev/null; then exit 1; fi; done
if run send +4670 '' >/dev/null; then exit 1; fi
touch "$dir/nosend"
if run send +4670 nope >/dev/null; then exit 1; fi
run list | grep -q '"status":"failed","text":"nope"'
rm "$dir/nosend"

# delete (both parts of the long message)
ids=$(echo "$out" | sed -n 's/.*"ids":\["\([0-9a-f]*\)","\([0-9a-f]*\)"\].*/\1 \2/p')
run delete $ids >/dev/null
if run list | grep -q 'سلام'; then exit 1; fi
run list | grep -q 'How are you'

# phone book
run contact-set +989120000000 'Ali "A"' >/dev/null; run contact-set +989120000000 Ali >/dev/null; run contact-set 0912 Sara >/dev/null
[ "$(run contacts)" = '[{"name":"Sara","number":"0912"},{"name":"Ali","number":"+989120000000"}]' ] ||
	[ "$(run contacts)" = '[{"name":"Ali","number":"+989120000000"},{"name":"Sara","number":"0912"}]' ]
if run contact-set 'x' y >/dev/null; then exit 1; fi
run contact-del 0912 >/dev/null; run contacts | grep -q Sara && exit 1

# API keys and the HTTP API
key=$(run key-add laptop | sed -n 's/.*"key":"\([0-9a-f]*\)".*/\1/p'); [ ${#key} = 48 ]
if grep -q "$key" "$X28_SMS_DIR/keys"; then exit 1; fi   # only the hash is stored
api() { REQUEST_METHOD=$1 PATH_INFO=$2 HTTP_AUTHORIZATION="Bearer $3" CONTENT_LENGTH=${#4} run cgi <<BODY
$4
BODY
}
api GET /messages "$key" '' | grep -q '^Status: 200'
api GET /messages "$key" '' | grep -q 'How are you'
api GET /messages 00ff '' | grep -q '^Status: 401'
api GET /messages '' '' | grep -q '^Status: 401'
api GET /other "$key" '' | grep -q '^Status: 404'
api POST /messages "$key" 'to=%2B4670&text=a+b%21' | grep -q '^Status: 200'
run list | grep -q '"number":"+4670","status":"sent","text":"a b!"'
api POST /messages "$key" 'to=abc&text=x' | grep -q '^Status: 400'
id=$(run keys | sed -n 's/.*"id":"\([0-9a-f]*\)".*/\1/p'); run key-del "$id" >/dev/null
api GET /messages "$key" '' | grep -q '^Status: 401'

# webhook address and the hourly limit
if run webhook 'ftp://x' >/dev/null; then exit 1; fi
run webhook 'http://192.168.70.10:8080/sms' >/dev/null; run webhook | grep -q '"url":"http://192.168.70.10:8080/sms"'
run webhook '' >/dev/null; run webhook | grep -q '"url":""'
i=0; while run send +4670 "n$i" >/dev/null; do i=$((i + 1)); [ "$i" -lt 40 ]; done
run send +4670 more | grep -q 'rate limit'
echo "x28-telephony: ok"
