# Telephony: text messages, phone book, API

`package/x28-telephony` gives the native image what the vendor firmware had for the SIM's text messages, and an HTTP API so other
machines on the LAN can use the SIM (issues #309 and #15). Calls are not in it yet; [what is known](#calls-not-built-yet) is at the end.

**State (2026-11-12):** installed by hand on the X28 test unit. Receiving, the store and the HTTP API work there; a sent test message arrived;
**the LuCI pages in a browser are not yet checked**. See [Not verified](#not-verified).

## What you get

- **LuCI, Services > Telephony**, three tabs: **Messages** (received and sent, newest first, reply, delete, send), **Phone book**
  (names for numbers; kept on the router, not on the SIM), **API** (keys, the address for received messages, examples).
- **`/usr/sbin/x28-sms`**, the one backend (Lua 5.1). `x28-sms` without arguments lists its commands; output is JSON.
- **A service** (`/etc/init.d/x28-telephony`) that looks at the SIM every 15 seconds.

## How messages are kept

The SIM has 50 slots. A received message is copied to `/etc/x28-telephony/messages` and **only then deleted from the SIM**, so the
SIM does not fill up. A message the router cannot read stays on the SIM, and so do drafts and delivery reports. Sent messages are
kept in the same file, with `sent` or `failed`. The directory is root-only and is kept across `sysupgrade`
(`/lib/upgrade/keep.d/x28-telephony`). Long messages arrive in parts; they are stored as parts and shown joined.

## HTTP API

Create a key in the API tab (it is shown once; only its SHA-256 is stored). All calls need `Authorization: Bearer <key>`. The
router redirects HTTP to HTTPS and its certificate is self-signed, hence `-k`.

```sh
# all messages, oldest first
curl -k -H "Authorization: Bearer $KEY" https://192.168.70.1/cgi-bin/x28-telephony/messages

# send (form or JSON)
curl -k -H "Authorization: Bearer $KEY" --data-urlencode to=+989121234567 --data-urlencode "text=Hello" \
  https://192.168.70.1/cgi-bin/x28-telephony/messages
curl -k -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d '{"to":"+989121234567","text":"Hello"}' \
  https://192.168.70.1/cgi-bin/x28-telephony/messages
```

| Answer | Meaning |
|---|---|
| `200` `{"ok":true}` or a list | done |
| `400` | bad number, empty or too long text (10 parts: 1530 GSM characters, 670 otherwise) |
| `401` | no key or a wrong one |
| `429` | more than 30 messages sent in the last hour (API and LuCI together) |
| `502` | the modem refused the message; it is kept as `failed` |

A message is `{"ids":[...],"dir":"in"|"out","number":...,"time":<Unix time>,"status":...,"text":...,"complete":true|false}`.

**Received messages** can also be pushed: set an address in the API tab and each complete message is POSTed there as that JSON.
A long message is pushed once, when its last part is in; if a part never arrives it is not pushed.

The API is reachable from wherever LuCI is reachable (the LAN, by the default firewall). Nothing is sent without an explicit call.

## How it talks to the modem

Through `mipc_wan_cli --at_cmd`, in PDU mode: `AT+CPMS?` for the count, `AT+CMGR=<slot>` to read, `AT+CMGD=<slot>` to delete,
`AT+CMGS=<length>,"<pdu>"` to send. Two things were learned on the unit:

- `mipc_wan_cli --at_cmd 'AT+CMGL=4'` (list everything) **crashes the CLI** when the answer is long (27 messages). So slots are
  read one at a time, and only when the SIM's count changed.
- The CLI cannot answer the `> ` prompt of the standard two-step `AT+CMGS`. The one-line form above is MediaTek's, and this modem
  accepts it through the CLI.

## Check

```sh
lua package/x28-telephony/files/x28-sms selftest   # coding and decoding, no modem
sh tests/test_telephony.sh                         # the whole tool against a fake modem (needs lua 5.1 and flock)
```

## Not verified

- Sending **Persian text** or a message of **several parts** (only a short GSM-alphabet message was sent).
- The **LuCI pages in a browser** (the three views are served and the menu entry is in place; nobody has clicked through them).
- Installing as an **ipk** from the feed (the files were copied by hand), and the image.
- The push of received messages to an address, a message arriving while the service runs, and `sysupgrade` keeping the store.
- The X28 PRO.

Verified on the X28 test unit, 2026-11-12, files copied to their package paths:

| Check | Result |
|---|---|
| `x28-sms selftest` and `tests/test_telephony.sh` on the unit's Lua 5.1.5 and busybox | pass |
| Raw copy of the SIM's 27 slots to a root-only file first | 27 PDUs |
| `x28-sms poll` | `{"new":27}`; `AT+CPMS?` went from 27 to 0 of 50; the store shows 6 complete messages (2 to 8 parts each, Persian text, named senders) |
| A second poll | `{"new":0}`, no slot read |
| API from another machine over HTTPS: `GET` with a key | `200`, the 6 messages |
| API without a key, with a wrong one, with a revoked one | `401` |
| API `POST` with a bad number (form and JSON) and with empty text | `400`, nothing sent |
| Service enabled and started | running under procd |
| `x28-sms send` of one short GSM-alphabet message to a number the owner named | the modem answered `+CMGS:` in 0.3 s through the one-line `AT+CMGS=<length>,"<pdu>"` form; stored as `sent`; the owner confirmed it arrived on the phone |

## Calls (not built yet)

The goal: a phone on the PRO's RJ11 socket calls through the SIM, as stock does. Read-only findings on the X28 test unit:

| Piece | Found |
|---|---|
| Registration for calls | `AT+CIREG?` gives `2,0,0`: IMS (VoLTE) is **not registered** with this SIM, so calls cannot work yet (#16) |
| Call control | `mipc_wan_cli` has `dial_request`, `answer_ringing`, `hangup_all`, `get_call_status`, `set_speech`, `dtmf_detect`, `play_tone`, `ims_get_status`, `ims_set_config`; none was run |
| Phone socket | device tree has `silabs,proslic_spi`; `/dev/ql_slic` and `libqlslic.so` are in the image |
| Audio | ALSA card `mt6880-mt6359` with many PCM devices; `/dev/ccci_aud` (#17) |

Order of work: IMS registration (#16), then the audio path (#17), then the SLIC on a PRO (hook, ring, DTMF), then joining them.
