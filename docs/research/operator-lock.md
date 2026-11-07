# The stock firmware's operator (SIM) lock

Some X28 units from an operator refuse other operators' SIMs. This note records how the stock firmware (slot B) implements that lock, from the
stock `rootfs_b` image and the `user_config` partition of five full backups, and how to clear it by hand. Nothing here was run on a locked unit:
every backup we have is from an already unlocked unit, so the unlock steps are inferred and marked as such.

## What was read

| Source | Finding |
|---|---|
| `rootfs_b`, `/tzwww/js/advance/unlockIndex.js` | The web page "SIM lock" is `unlock.html` (an NCK code field), except for region code `MY0588`, which shows `lockPlmn.html` instead. |
| `/tzwww/js/advance/unclok.js` | The NCK page posts command `UNLOCK_SIM` (340) with `unlock_nck_code`; its GET returns `remainCount` (attempts left) and `functionSwitch`. It disables the field when either is `0`. |
| `/tzwww/js/advance/lockPlmn.js` | The PLMN page posts `LOCK_PLMN` (219) with `lockPlmn` = `1` or `0` and `lockPlmnList`, a comma-separated list of up to 64 PLMNs (MCC+MNC). |
| `http.cgi` strings | `SYS_UNLOCK_NCK_CODE_COUNT`, `SYS_UNLOCK_SIM_CODE_ENABLE`, `SYS_UNLOCK_SIM_NCK_CODE`, the flag files `/mnt/data/var/run/nck_unlock_success` and `nck_unlock_failed`, and the message "nck code limit, function close". |
| `usr/bin/dialer`, `usr/bin/configloader` strings | Both read `SYS_LOCK_OPERATOR_SW` and `SYS_LOCK_OPERATOR_LIST`; `dialer` also uses `/mnt/data/etc/tzcfg/sim_lock_file` and `apn_imsi`. |
| `/etc/init.d/0mount_all` | `/mnt/data` is the `user_config` partition (mtd48), mounted as yaffs2. |
| `user_config` of five backups | A shell-style settings file (`system_config.use`) with lines `export KEY="value"`. In all five: `SYS_LOCK_OPERATOR_SW="0"`, `SYS_LOCK_OPERATOR_LIST=""`, `SYS_LOCK_SIM_SW="0"`, `SYS_LOCK_PHONE_SW="0"`. No `sim_lock_file` is present. |

## How the lock works

Two mechanisms sit side by side in the stock config:

1. **Operator (PLMN) lock**: `SYS_LOCK_OPERATOR_SW` is `1` and `SYS_LOCK_OPERATOR_LIST` names the allowed operators. This is the setting the
   `lockPlmn` page edits. The `dialer` daemon reads it when it brings the modem up.
2. **Network-control-key (NCK) lock**: the 3GPP network personalisation lock. The user types the operator's NCK code on the "SIM lock" page and the
   firmware keeps an attempt counter (`SYS_UNLOCK_NCK_CODE_COUNT`). When the counter reaches zero the page closes for good ("nck code limit,
   function close"). The lock state itself lives in the modem, not in a Linux file.

`SYS_LOCK_SIM_SW`, `SYS_LOCK_SIM_INITIAL_PIN` and `SYS_LOCK_SIM_CHANGED_PIN` sit next to them but look like the SIM **PIN** feature, and
`SYS_LOCK_PHONE_SW` like a phone lock. They are not operator locks; leave them alone.

## How to clear the operator lock by hand (inferred, not tested on a locked unit)

This only helps with mechanism 1. It does nothing for an NCK lock: without the operator's code, do not guess; the counter is not renewable.

You need root SSH on the stock slot B: the flasher's **Root access** step (key-only SSH on port 22, or 2222). Then:

```sh
# 1. find the settings file and keep a copy (on the modem and on your computer)
F=/mnt/data/etc/tzcfg/system_config.use
[ -f "$F" ] || F=$(find /mnt/data -name system_config.use | head -1)
cp "$F" "$F.before-unlock"
cat "$F" > /tmp/system_config.use      # then copy /tmp/system_config.use to your computer (ssh ... 'cat F' > file)

# 2. look at the two keys; each must appear exactly once
grep -E '^export SYS_LOCK_OPERATOR_(SW|LIST)=' "$F"

# 3. clear them: switch off, empty list (only these two lines change)
sed -e 's/^export SYS_LOCK_OPERATOR_SW=.*/export SYS_LOCK_OPERATOR_SW="0"/' \
    -e 's/^export SYS_LOCK_OPERATOR_LIST=.*/export SYS_LOCK_OPERATOR_LIST=""/' "$F" > "$F.new"
grep -E '^export SYS_LOCK_OPERATOR_(SW|LIST)=' "$F.new"      # check, then
cat "$F.new" > "$F" && rm "$F.new" && sync
```

Rollback: `cp "$F.before-unlock" "$F" && sync`.

Then let the stock firmware read the file again. A reboot is the sure way, but **do not reboot the stock slot casually**: stock B repairs, that is
erases, slot A when A's boot tries are above 3 (see [slot-selection](slot-selection.md) and `docs/RECOVERY.md`). Check A's tries first, or use the
web page below.

On a unit with region code `MY0588` the stock web UI does the same thing itself: Advanced, **SIM lock**, switch the PLMN lock off and save.

## What is not known

- The exact directory of `system_config.use` (the file name is seen in the `user_config` image; `/mnt/data/etc/tzcfg/` is where `dialer` keeps its
  related files). The commands above search for it.
- Whether the firmware writes its in-memory copy back over the file before the next read (the web UI would then be the way to change it).
- Whether a unit that refuses other operators sets exactly these two keys, or also creates `sim_lock_file`. We have no locked unit or backup of one.

If you have a locked unit, reading the two keys (step 2 only, read-only) and posting them in an issue would settle the first and third points.
