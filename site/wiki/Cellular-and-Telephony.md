# Cellular and telephony

## The WAN: `x28_mipc`

The 5G connection is an ordinary netifd protocol. It appears in LuCI under Network > Interfaces like any other, UCI holds the
configuration, and netifd gets the bearer device (`ccmniN`), addresses, route and DNS.

```
config interface 'wan'
    option proto 'x28_mipc'
    option apn ''          # empty = read from the SIM
    option iptype '3'      # IPv4, IPv6 or IPv4v6
```

| Option | Values | Effect |
|---|---|---|
| `apn` | text or empty | empty reads the APN for the SIM from the stock APN database |
| `iptype` | v4 / v6 / v4v6 | changing it (or the APN) re-attaches the modem: up to about 40 s offline |
| `roaming` | `0` (default) / `1` | with `0`, setup fails with `ROAMING_DISABLED` while roaming |
| `netmode` | `auto` / `4g` / `5g` | radio technology. Only `auto` was run on a unit; SA/NSA choice is not offered |
| `lteband_mode` + `lteband_list` | `none` / `allow` / `deny` | LTE band lock |
| `nrband_mode` + `nrband_list` | same | 5G band lock, through `x28-nrband` |
| `celllock` | `<earfcn>:<pci>` | LTE cell lock. 5G cells cannot be locked |

The **Carrier tab** shows operator, registration, signal, 5G (EN-DC) state and the serving and neighbour cells, offers a network
scan for manual operator selection, and lists those cells as lock choices. A new option only reaches the script after netifd
restarts (`/etc/init.d/network restart`).

### Locks

Locks are **strict**: one that took effect stays, even without service. Only you remove it.

| Undo by hand | Command |
|---|---|
| Cell lock | `mipc_wan_cli --at_cmd 'at+emmchlck=0'` |
| Network mode | `mipc_wan_cli --nw_set_rat 19` |
| 5G bands | `x28-nrband set 080800d5 000001a0 00003000` |
| 4G bands | `mipc_wan_cli --at_cmd 'at+epbse=154,145,2282225877,1952,0,0,0,0,0,0'` |

### How it behaves

- Refuses to start while the vendor `wan_mgr` runs.
- Serializes its own operations and validates every modem reply.
- On teardown, deactivates only the bearer (CID) it activated. It never kills processes or edits DHCP or firewall config.
- Syncs the attach APN before the data call; without that, a PDN whose APN differs from the attach APN is refused.

### Found the hard way

| Finding | Consequence |
|---|---|
| The kernel leaves `ccmniN` down after the data call | the protocol brings the device up itself; before, it looped |
| `mtk_netagent` forces `CFUN 0/4` in this start order | it is not started; the protocol handles IPv6 |
| The image missed `/etc/conf/apns-conf_8.xml` | first boot looped on `NO_SIM_APN`; the file is now copied from stock |
| `AT+QENG` and friends return `+CME ERROR: 100` | 5G state comes from MIPC messages, with ids read from `ql_ril_service` in Ghidra |
| `sms_mgr -h` rebooted the device | never run vendor binaries with unknown flags |

### Limits

One cellular WAN. No PAP/CHAP, no SIM PIN entry. One SIM and one carrier tested. Reconnect after a modem reset is seen to work
but not soak-tested. The NR signal field order is inferred: check it against another source before relying on the numbers.

## Text messages (`x28-telephony`, since v1.1.0)

- **LuCI, Services > Telephony:** Messages (conversations by number, reply box, paging), Phone book (kept on the router), API (keys,
  push address, examples).
- **Backend:** `/usr/sbin/x28-sms` (Lua 5.1, JSON output).
- **Service:** looks at the SIM every 15 seconds.

A received message is copied to `/etc/x28-telephony/messages` and **only then** deleted from the SIM, so the SIM's 50 slots do
not fill up. The store is root-only and is in the sysupgrade keep list.

### HTTP API

Create a key in the API tab (shown once; only its SHA-256 is stored).

```sh
curl -k -H "Authorization: Bearer $KEY" https://192.168.70.1/cgi-bin/x28-telephony/messages
curl -k -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"to":"+989121234567","text":"Hello"}' https://192.168.70.1/cgi-bin/x28-telephony/messages
```

| Answer | Meaning |
|---|---|
| `200` | done |
| `400` | bad number, empty or too long text |
| `401` | no key or a wrong one |
| `429` | more than 30 messages sent in the last hour |
| `502` | the modem refused; the message is kept as `failed` |

Received messages can also be pushed to an address you set. The API is reachable wherever LuCI is (the LAN by default).

### Modem quirks

- `AT+CMGL=4` crashes `mipc_wan_cli` when the answer is long, so slots are read one at a time.
- The CLI cannot answer the `> ` prompt of two-step `AT+CMGS`; MediaTek's one-line form `AT+CMGS=<length>,"<pdu>"` works.

### Not verified

Sending Persian or multi-part text, the push to an address, `sysupgrade` keeping the store, install as an ipk from the feed, the
PRO.

## Voice calls: connect, but no audio

Goal: a phone on the PRO's RJ11 socket calls through the SIM. **Not shipped.** Experiments on a test unit (MCI, Iran, 432/11)
got as far as a connected call with no sound.

### What works

| Step | Result |
|---|---|
| IMS registration | registers after setting the modem's `operator_code` to 16386 (`AT+ECFGGET`/`ECFGSET`); before that it stayed unregistered. `AT+CIREG?` = `2,1,5` |
| IMS APN | CID 1 `ims`, IPv4v6, next to the internet APN on CID 0 |
| Call set-up | incoming and outgoing (`ATD`) calls reach the **active** state: `AT+CLCC` shows the call, mode 20 |
| Voice daemons | the stock `speech_daemon`, `libmodem-afe-ctrl-server-bin` and `audio-ctrl-service` run and connect to the modem (`/dev/ccci_aud`) |

### What does not

- The modem never sets up a **dedicated voice bearer** (QCI 1): `AT+CGEQOSRDP` is empty and `AT+CGCONTRDP` lists only the
  internet and default `ims` bearers.
- No speech path starts: no ALSA stream opens and `speech_daemon` logs no speech-on message.
- The network clears every call about **20 s after answer** (`AT+CEER` = `16,CM_NORMAL_CALL_CLR`).
- The same SIM does VoLTE in a phone, and there is no CS fallback on this network (`AT+CREG?` = `0,6`, SMS only).

### Tried without effect

Each with a real call, then rolled back: `voice_support` 0/1; `operator_code` 16386/0; the MCC/MNC whitelist from a public
MediaTek guide for MCI; 4G only versus 4G/5G NSA; `AT+CEUS` 0/1; incoming versus outgoing.

### Open questions (drafted as a support request to Quectel)

1. Which carrier profile or `AT+QCFG` / `AT+ECFGSET` keys make this build request the voice bearer on MCI? `AT+EMCFC=4,0/1/2`
   returns empty paths, so the MCI profile may be missing from the firmware.
2. What `AT+CLCC` mode 20 means here, and whether the call is really carried over IMS.
3. How to see the SIP exchange and bearer set-up from an embedded-Linux host.
4. Whether the firmware supports call audio over the SoC speech interface without an Android audio HAL.

### Still to do after audio

The PRO's phone socket (`silabs,proslic_spi` in the device tree, `/dev/ql_slic`, `libqlslic.so`): hook, ring, DTMF. Then a
package. Issues: #16 (IMS), #17 (audio path).

This work is not in `docs/` yet; the record is a research note on a branch, to be merged.

Full documents: [NATIVE-CELLULAR](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/NATIVE-CELLULAR.md),
[TELEPHONY](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/TELEPHONY.md),
[modem driver analysis](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/x28-modem-driver-analysis.md),
[operator lock](https://github.com/mralinp/zlt-x28-openwrt/blob/main/docs/research/operator-lock.md).
