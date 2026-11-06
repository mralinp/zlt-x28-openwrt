#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Stage mock-only tests under /tmp; never install or invoke a real modem CLI."""
import argparse
import json
import pathlib
import shlex
import subprocess
import tarfile
import tempfile
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = {"apn": "example.invalid", "mtu": 1500, "iptype": 1}
REPLY = {"result": 0, "cid": 4, "ifname": "ccmni7", "v4_addr": "198.51.100.7",
         "v4_mask": "255.255.255.255", "v4_gw": "0.0.0.0",
         "v4_dns1": "192.0.2.53", "v4_dns2": "192.0.2.53"}
V6 = {"v6_addr": "fe80::1:0:73a4:e064", "v6_gw": "", "v6_dns1": "2001:db8::53", "v6_dns2": "2001:db8::53"}
RA = "    inet6 2001:db8:1:2:1:0:73a4:e064/64 scope global dynamic flags 100 \n"

def case(name, *, config=None, reply=None, error=None, cleanup=False, **extra):
    return {"name": name, "config": {**CONFIG, **(config or {})},
            "reply": {**REPLY, **(reply or {})}, "error": error, "cleanup": cleanup,
            "sim": "MIPC_SIM_STATUS_COMPLETE_READY", "activate_rc": 0,
            "deactivate_rc": 0, "notify_rc": 0, "link": "up", "operation": "setup",
            "vendor_active": 0, "status_rc": 0, "status": {}, "sim_apns": "MCI\tmcinet\tIPV4V6\n", "v6_global": RA, **extra}

def cases():
    own = {"data": {"x28_mipc_cid": 4, "x28_mipc_owner": "wan"}}
    return [
        case("point-to-point"),
        case("attach-sync-apn", ia="IA apn:mcinet pdp_type:1 roaming_type:3 bearer_bitmask:0xffffffff\n",
             expect_cmds=["--apn_ia_set example.invalid 1 3", "--at_cmd at+cfun=0", "--at_cmd at+cfun=1", "--data_call_act"]),
        case("attach-sync-iptype", ia="IA apn:example.invalid pdp_type:3 roaming_type:3 bearer_bitmask:0xffffffff\n",
             expect_cmds=["--apn_ia_set example.invalid 1 3", "--at_cmd at+cfun=1", "--data_call_act"]),
        case("attach-sync-no-profile", ia="", expect_cmds=["--apn_ia_set example.invalid 1 3", "--data_call_act"]),
        case("attach-set-failed", ia="", ia_set_noop=1, error="ATTACH_FAILED", no_activate_call=True,
             no_cfun=True),
        case("attach-cfun-lost", ia="", cfun_ok=0, error="ATTACH_FAILED", no_activate_call=True,
             expect_cmds=["--apn_ia_set", "--at_cmd at+cfun=0", "--at_cmd at+cfun=1"]),
        case("in-sync-unregistered", reg=0, error="ATTACH_FAILED", no_activate_call=True, no_ia_set=True,
             expect_cmds=["--at_cmd at+cfun=1"]),
        case("leading-dash-apn", config={"apn": "-x"}, error="INVALID_CONFIG", no_cli=True),
        case("attach-no-registration", ia="", reg=0, error="ATTACH_FAILED", no_activate_call=True),
        case("operator-manual", config={"plmn": "43235"}, expect_cmds=['--at_cmd at+cops=1,2,"43235"', "--data_call_act"]),
        case("operator-error-but-applied", config={"plmn": "43235"}, cops_err_applied=1,
             expect_cmds=['--at_cmd at+cops=1,2,"43235"', "--data_call_act"]),
        case("operator-already", config={"plmn": "43211"}, cops="1 43211", no_cops_set=True),
        case("operator-back-to-auto", cops="1 43235", expect_cmds=["--at_cmd at+cops=0", "--data_call_act"]),
        case("operator-rejected", config={"plmn": "43235"}, cops_set_ok=0, error="OPERATOR_FAILED", no_activate_call=True,
             expect_cmds=['--at_cmd at+cops=1,2,"43235"', "--at_cmd at+cops=0"]),
        case("operator-never-registers", config={"plmn": "43235"}, cops_noop=1, error="OPERATOR_FAILED", no_activate_call=True,
             expect_cmds=['--at_cmd at+cops=1,2,"43235"', "--at_cmd at+cops=0"]),
        case("operator-short", config={"plmn": "4321"}, error="INVALID_CONFIG", no_cli=True),
        case("operator-nondigit", config={"plmn": "43x11"}, error="INVALID_CONFIG", no_cli=True),
        case("cell-lock-set", config={"celllock": "42090:258"},
             expect_cmds=["--at_cmd at+emmchlck=1,7,0,42090,258", "--data_call_act"]),
        case("cell-lock-already", config={"celllock": "42090:258"}, lock="1,7,0,42090,258,0", no_lock_set=True),
        case("cell-lock-off", lock="1,7,0,42090,258,0", expect_cmds=["--at_cmd at+emmchlck=0", "--data_call_act"]),
        # reg=0 means no registration at all, so setup later stops at the attach step; the lock was set once and not removed.
        case("cell-lock-no-service-kept", config={"celllock": "42090:258"}, reg=0, error="ATTACH_FAILED", no_activate_call=True,
             one_lock_set=True, no_lock_clear=True, expect_cmds=["--at_cmd at+emmchlck=1,7,0,42090,258"]),
        case("cell-lock-not-applied", config={"celllock": "42090:258"}, lock_noop=1, error="CELL_LOCK_FAILED", no_activate_call=True,
             one_lock_set=True, no_lock_clear=True, expect_cmds=["--at_cmd at+emmchlck=1,7,0,42090,258"]),
        case("cell-lock-stale-kept", config={"celllock": "42090:258"}, lock="1,7,0,42090,258,0", reg=0,
             error="ATTACH_FAILED", no_activate_call=True, no_lock_set=True, no_lock_clear=True),
        # an operator that fails must not hide the clearing of a lock that is still on the modem
        case("cell-clear-despite-operator-failure", config={"plmn": "43235"}, cops_set_ok=0, lock="1,7,0,42090,258,0",
             error="OPERATOR_FAILED", no_activate_call=True, expect_cmds=["--at_cmd at+emmchlck=0", '--at_cmd at+cops=1,2,"43235"']),
        case("cell-lock-off-unreadable", lock="garbage", expect_cmds=["--at_cmd at+emmchlck=0", "--data_call_act"]),
        case("cell-lock-leading-zero", config={"celllock": "042090:258"}, error="INVALID_CONFIG", no_cli=True),
        case("cell-lock-pci-leading-zero", config={"celllock": "42090:0258"}, error="INVALID_CONFIG", no_cli=True),
        case("cell-lock-huge", config={"celllock": "99999999999999999999:1"}, error="INVALID_CONFIG", no_cli=True),
        case("cell-lock-zero-ok", config={"celllock": "0:0"}, expect_cmds=["--at_cmd at+emmchlck=1,7,0,0,0", "--data_call_act"]),
        case("band-allow", config={"lteband_mode": "allow", "lteband_list": [38, 40, 41, 42]},
             expect_cmds=["--at_cmd at+epbse=154,145,0,928,0,0,0,0,0,0", "--data_call_act"]),
        case("band-deny", config={"lteband_mode": "deny", "lteband_list": [1]},
             expect_cmds=["--at_cmd at+epbse=154,145,2282225876,1952,0,0,0,0,0,0", "--data_call_act"]),
        case("band-none-unchanged", config={"lteband_mode": "none"}, no_epbse_set=True),
        case("band-unset-untouched", no_epbse_any=True),
        case("band-none-restores", config={"lteband_mode": "none"}, epbse="154,145,0,928,0,0,0,0,0,0",
             expect_cmds=["--at_cmd at+epbse=154,145,2282225877,1952,0,0,0,0,0,0", "--data_call_act"]),
        case("band-nothing-left", config={"lteband_mode": "deny", "lteband_list": [1, 3, 5, 7, 8, 20, 28, 32, 38, 40, 41, 42, 43]}, error="BAND_LOCK_FAILED",
             no_activate_call=True, no_epbse_set=True),
        case("band-not-applied", config={"lteband_mode": "allow", "lteband_list": [42]}, epbse_noop=1, error="BAND_LOCK_FAILED",
             no_activate_call=True, one_epbse_set=True, expect_cmds=["--at_cmd at+epbse=154,145,0,512,0,0,0,0,0,0"]),
        # reg=0 means no registration at all, so setup later stops at the attach step; the lock was set once and not undone.
        case("band-no-service-kept", config={"lteband_mode": "allow", "lteband_list": [42]}, reg=0, one_epbse_set=True,
             error="ATTACH_FAILED", no_activate_call=True, expect_cmds=["--at_cmd at+epbse=154,145,0,512,0,0,0,0,0,0"]),
        case("band-bad-mode", config={"lteband_mode": "x"}, error="INVALID_CONFIG", no_cli=True),
        case("band-unsupported", config={"lteband_mode": "allow", "lteband_list": [2]}, error="INVALID_CONFIG", no_cli=True),
        case("nr-allow", config={"nrband_mode": "allow", "nrband_list": [78]},
             expect_cmds=["x28-nrband set 00000000 00000000 00002000", "--data_call_act"]),
        case("nr-deny", config={"nrband_mode": "deny", "nrband_list": [77]},
             expect_cmds=["x28-nrband set 080800d5 000001a0 00002000", "--data_call_act"]),
        case("nr-none-unchanged", config={"nrband_mode": "none"}, no_nr_set=True),
        case("nr-unset-untouched", no_nr_any=True),
        case("nr-none-restores", config={"nrband_mode": "none"}, nrcur="00000000 00000000 00002000",
             expect_cmds=["x28-nrband set 080800d5 000001a0 00003000", "--data_call_act"]),
        case("nr-nothing-left", config={"nrband_mode": "deny", "nrband_list": [1, 3, 5, 7, 8, 20, 28, 38, 40, 41, 77, 78]},
             error="NRBAND_LOCK_FAILED", no_activate_call=True, no_nr_set=True),
        case("nr-not-applied", config={"nrband_mode": "allow", "nrband_list": [78]}, nr_noop=1, error="NRBAND_LOCK_FAILED",
             no_activate_call=True, one_nr_set=True, expect_cmds=["x28-nrband set 00000000 00000000 00002000"]),
        case("nr-no-service-kept", config={"nrband_mode": "allow", "nrband_list": [78]}, reg=0, one_nr_set=True,
             error="ATTACH_FAILED", no_activate_call=True, expect_cmds=["x28-nrband set 00000000 00000000 00002000"]),
        case("nr-missing-helper", config={"nrband_mode": "allow", "nrband_list": [78]}, nr_missing=1, error="NRBAND_LOCK_FAILED",
             no_activate_call=True),
        case("nr-none-missing-helper", config={"nrband_mode": "none"}, nr_missing=1),
        case("nr-none-helper-broken", config={"nrband_mode": "none"}, nr_getfail=1),
        case("nr-allow-helper-broken", config={"nrband_mode": "allow", "nrband_list": [78]}, nr_getfail=1,
             error="NRBAND_LOCK_FAILED", no_activate_call=True),
        case("nr-none-garbage-helper", config={"nrband_mode": "none"}, nrcur="zz zz zz"),
        case("nr-allow-garbage-helper", config={"nrband_mode": "allow", "nrband_list": [78]}, nrcur="zz zz zz",
             error="NRBAND_LOCK_FAILED", no_activate_call=True, no_nr_set=True),
        case("nr-none-widen-fails", config={"nrband_mode": "none"}, nrcur="00000000 00000000 00002000", nr_noop=1, one_nr_set=True,
             expect_cmds=["x28-nrband set 080800d5 000001a0 00003000", "--data_call_act"]),
        case("nr-bad-mode", config={"nrband_mode": "x"}, error="INVALID_CONFIG", no_cli=True),
        case("nr-unsupported-band", config={"nrband_mode": "allow", "nrband_list": [2]}, error="INVALID_CONFIG", no_cli=True),
        case("cell-lock-no-pci", config={"celllock": "42090"}, error="INVALID_CONFIG", no_cli=True),
        case("cell-lock-big-earfcn", config={"celllock": "46590:258"}, error="INVALID_CONFIG", no_cli=True),
        case("cell-lock-big-pci", config={"celllock": "42090:512"}, error="INVALID_CONFIG", no_cli=True),
        case("cell-lock-junk", config={"celllock": "42090:25x"}, error="INVALID_CONFIG", no_cli=True),
        case("roaming-off", reg=5, error="ROAMING_DISABLED", no_activate_call=True, no_ia_set=True),
        case("roaming-on", reg=5, config={"roaming": True}),
        case("roaming-invalid", config={"roaming": 2}, error="INVALID_CONFIG", no_cli=True),
        case("gateway", reply={"v4_gw": "198.51.100.1", "v4_mask": "255.255.255.0"}),
        case("no-route-dns", config={"defaultroute": False, "peerdns": False}),
        case("bad-apn", config={"apn": "x;touch /tmp/should-not-exist"}, error="INVALID_CONFIG", no_cli=True),
        case("bad-mtu", config={"mtu": 575}, error="INVALID_CONFIG", no_cli=True),
        case("ipv4v6", config={"iptype": 3}, reply=V6),
        case("ipv4v6-v4-only", config={"iptype": 3}, v6_global=""),
        case("ipv6-only", config={"iptype": 2}, reply={**V6, "v4_addr": "", "v4_mask": ""}),
        case("ipv6-missing", config={"iptype": 2}, v6_global="", error="NO_IPV6", cleanup=True),
        case("ipv4v6-late-v6", config={"iptype": 3}, get={"iface": "ccmni7", **V6}),
        case("late-v6-other-iface", config={"iptype": 3}, get={"iface": "ccmni1", **V6}, v6_global=""),
        case("ipv4v6-no-ra", config={"iptype": 3}, reply=V6, v6_global=""),
        case("ipv6-only-no-ra", config={"iptype": 2}, reply={**V6, "v4_addr": "", "v4_mask": ""}, v6_global="",
             error="NO_IPV6", cleanup=True, early_up=True),
        case("bad-ipv6", config={"iptype": 3}, reply={**V6, "v6_addr": "2001:db8::zz"}, error="INVALID_REPLY", cleanup=True),
        case("bad-iptype", config={"iptype": 4}, error="INVALID_CONFIG", no_cli=True),
        case("auto-apn", config={"apn": ""}, expect_apn="mcinet"),
        case("no-sim-apn", config={"apn": ""}, sim_apns="", error="NO_SIM_APN", no_activate=True),
        case("vendor-active", vendor_active=1, error="VENDOR_WAN_ACTIVE", no_cli=True),
        case("sim-locked", sim="MIPC_SIM_STATUS_SIM_PIN", error="SIM_PIN_LOCKED", no_activate=True),
        case("sim-pending", sim="MIPC_SIM_STATUS_NOT_READY", error="SIM_NOT_READY", no_activate=True),
        case("activate-hang", act_hang=1, error="CONNECT_TIMEOUT",
             expect_cmds=["--data_call_act", "--at_cmd at+cfun=0", "--at_cmd at+cfun=1"]),
        case("activate-failed", activate_rc=1, error="CONNECT_FAILED"),
        case("malformed-json", raw_reply="not json", error="INVALID_REPLY"),
        case("modem-rejected", reply={"result": 7}, error="CONNECT_FAILED"),
        case("rejected-without-cid", reply={"result": 7, "cid": None}, error="CONNECT_FAILED"),
        case("invalid-cid", reply={"cid": "4;bad"}, error="INVALID_REPLY"),
        case("foreign-device", reply={"ifname": "eth0"}, error="INVALID_REPLY", cleanup=True),
        case("bad-address", reply={"v4_addr": "999.1.2.3"}, error="INVALID_REPLY", cleanup=True),
        case("trailing-address-dot", reply={"v4_addr": "198.51.100.7."}, error="INVALID_REPLY", cleanup=True),
        case("bad-mask", reply={"v4_mask": "255.0.255.0"}, error="INVALID_REPLY", cleanup=True),
        case("zero-mask", reply={"v4_mask": "0.0.0.0"}, error="INVALID_REPLY", cleanup=True),
        case("bad-gateway", reply={"v4_gw": "1.2.3.999"}, error="INVALID_REPLY", cleanup=True),
        case("bad-dns", reply={"v4_dns1": "1.2.3.999"}, error="INVALID_REPLY", cleanup=True),
        case("link-down", link="down", error="LINK_NOT_READY", cleanup=True),
        case("notify-failed", notify_rc=1, error="NOTIFY_FAILED", cleanup=True),
        case("cleanup-failed", reply={"v4_addr": "999.1.2.3"}, deactivate_rc=1,
             error="CLEANUP_FAILED", cleanup=True),
        case("lock-held", operation="locked", error="MODEM_BUSY", no_cli=True),
        case("own-teardown", operation="teardown", status=own, cleanup=True),
        case("empty-teardown", operation="teardown", status={"data": {}}),
        case("foreign-teardown", operation="teardown", status={"data": {"x28_mipc_cid": 4, "x28_mipc_owner": "other"}},
             error="OWNERSHIP_MISMATCH", no_cli=True),
        case("invalid-teardown", operation="teardown", status={"data": {"x28_mipc_cid": "4;bad", "x28_mipc_owner": "wan"}},
             error="OWNERSHIP_MISMATCH", no_cli=True),
        case("unavailable-status", operation="teardown", status_rc=1,
             error="STATUS_UNAVAILABLE", no_cli=True),
        case("failed-teardown", operation="teardown", status=own, deactivate_rc=1,
             error="DEACTIVATE_FAILED", cleanup=True),
    ]

def run(argv, **kwargs):
    result = subprocess.run(argv, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {result.stderr.strip()}")
    return result

def verify(item, directory):
    events = [json.loads(line) for line in (directory / "notifications").read_text().splitlines()]
    commands = (directory / "commands").read_text().splitlines()
    rc = int((directory / "exit_code").read_text())
    errors = [e for e in events if e.get("action") == 3]
    up = [e for e in events if e.get("action") == 0 and e.get("link-up")]
    assert not any("FORBIDDEN" in line or "--data_call_deact_apn" in line for line in commands), commands
    activations = [c for c in commands if c.startswith("--data_call_act ")]
    assert len(activations) <= 1, commands
    if activations:
        activation = json.loads(activations[0].split(" ", 1)[1])
        assert activation == {"apn": item.get("expect_apn", item["config"]["apn"]), "ip_type": item["config"]["iptype"], "roaming_type": 3,
                              "auth_type": 0, "username": "", "password": "",
                              "bearer_bitmask": "0xfffdffff", "mtu": item["config"]["mtu"], "mode": 1}, activation
    deactivations = [c for c in commands if c.startswith("--data_call_deact ")]
    assert deactivations == (["--data_call_deact 4"] if item["cleanup"] else []), commands
    want = item.get("expect_cmds") or []
    idx = [next(i for i, c in enumerate(commands) if c.startswith(w)) for w in want]
    assert idx == sorted(idx), commands
    if item.get("no_activate_call"):
        assert not activations, commands
    if item.get("no_cops_set"):
        assert not any(c.startswith("--at_cmd at+cops=1") or c.startswith("--at_cmd at+cops=0") for c in commands), commands
    if item.get("one_nr_set"):
        assert sum(c.startswith("x28-nrband set") for c in commands) == 1, commands
    if item.get("one_epbse_set"):
        assert sum(c.startswith("--at_cmd at+epbse=") for c in commands) == 1, commands
    if item.get("one_lock_set"):
        assert sum(c.startswith("--at_cmd at+emmchlck=1") for c in commands) == 1, commands
    if item.get("no_lock_clear"):
        assert not any(c == "--at_cmd at+emmchlck=0" for c in commands), commands
    if item.get("no_nr_set"):
        assert not any(c.startswith("x28-nrband set") for c in commands), commands
    if item.get("no_nr_any"):
        assert not any(c.startswith("x28-nrband") for c in commands), commands
    if item.get("no_epbse_set"):
        assert not any(c.startswith("--at_cmd at+epbse=") for c in commands), commands
    if item.get("no_epbse_any"):
        assert not any("epbse" in c for c in commands), commands
    if item.get("no_lock_set"):
        assert not any(c.startswith("--at_cmd at+emmchlck=") for c in commands), commands
    if item.get("no_cfun"):
        assert not any("cfun" in c for c in commands), commands
    if item.get("no_ia_set"):
        assert not any(c.startswith("--apn_ia_set") for c in commands), commands
    if item.get("no_cli"):
        assert not commands, commands
    if item.get("no_activate"):
        assert commands == ["--show_sim_status"], commands
    LL = {"ipaddr": "fe80::1:0:73a4:e064", "mask": "64"}
    if item["error"]:
        assert rc != 0 and any(item["error"] in e.get("error", []) for e in errors), (rc, events)
        if item["error"] != "NOTIFY_FAILED":
            # IPv6-only without an RA reported the link-local alone before giving up.
            assert all(u.get("ip6addr") == [LL] and not u.get("ipaddr") for u in up) if item.get("early_up") else not up, events
    else:
        assert rc == 0 and not errors, (rc, events)
        if item["operation"] == "setup":
            # A bearer with a link-local gets two updates: the link-local first (to solicit the RA), then the rest.
            ll = item["config"]["iptype"] != 1 and "fe80::1:0:73a4:e064" in (json.dumps(item["reply"]) + json.dumps(item.get("get") or {})) \
                and item["name"] != "late-v6-other-iface"
            assert len(up) == (2 if ll else 1) and all(u["interface"] == "wan" and u["ifname"] == "ccmni7" for u in up), events
            if ll:
                assert up[0]["ip6addr"] == [LL] and not up[0].get("ip6prefix"), events
            last = up[-1]
            v6 = item["name"] in ("ipv4v6", "ipv6-only", "ipv4v6-late-v6")
            if ll:
                assert (directory / "accept_ra").read_text() == "2\n", "router solicitation not enabled"
            if v6:
                assert (directory / "ip6del").read_text() == "2001:db8:1:2:1:0:73a4:e064/64\n", "kernel /64 not removed"
                assert (directory / "pinfo").read_text() == "0\n", "RA prefix info still accepted"
            elif ll:
                assert (directory / "pinfo").read_text() == "1\n" and not (directory / "ip6del").exists()
            if v6:
                assert last["ip6addr"] == [LL, {"ipaddr": "2001:db8:1:2:1:0:73a4:e064", "mask": "128"}], events
                assert last["ip6prefix"] == ["2001:db8:1:2::/64"], events
                assert any(r["target"] == "::" and r["netmask"] == "0" for r in last["routes6"]), events
            else:
                assert last.get("ip6addr", []) == ([LL] if ll else []) and not last.get("ip6prefix"), events
            if item["name"] == "ipv6-only":
                assert not last.get("ipaddr") and not last.get("routes"), events
                assert last["dns"] == ["2001:db8::53"], events
                return
            assert last["ipaddr"] == [{"ipaddr": "198.51.100.7", "mask": "24" if item["name"] == "gateway" else "32"}], events
            assert last["data"] == {"x28_mipc_cid": 4, "x28_mipc_owner": "wan"}, events
            if item["name"] == "no-route-dns":
                assert not last.get("routes") and not last.get("dns"), events
            else:
                assert last["dns"] == ["192.0.2.53"] + (["2001:db8::53"] if v6 else []), events
                route = last["routes"][0]
                assert route["target"] == "0.0.0.0" and route["netmask"] == "0", events
                assert route.get("gateway") == ("198.51.100.1" if item["name"] == "gateway" else None), events
        else:
            assert any(e.get("action") == 0 and e.get("link-up") is False for e in events), events

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--router", default="router", help="SSH alias for mock-only helper execution")
    args = parser.parse_args()
    script = ROOT / "package/x28-mipc/files/x28_mipc.sh"
    assert script.is_file(), "Native protocol handler has not been implemented"
    stage = "/tmp/x28-native-proto-test-" + uuid.uuid4().hex[:12]
    ssh = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", args.router]
    items = cases()
    with tempfile.TemporaryDirectory(prefix="x28-proto-") as tmp:
        tmp = pathlib.Path(tmp)
        for item in items:
            d = tmp / "cases" / item["name"]
            d.mkdir(parents=True)
            for field in ["config", "status"]:
                (d / field).write_text(json.dumps(item[field]))
            (d / "reply").write_text(item.get("raw_reply", json.dumps(item["reply"])))
            (d / "sim_apns").write_text(item["sim_apns"])
            (d / "v6_global").write_text(item["v6_global"])
            ia = item["ia"] if "ia" in item else "IA apn:%s pdp_type:%s roaming_type:3 bearer_bitmask:0xffffffff\n" % (
                item.get("expect_apn", item["config"]["apn"]), item["config"]["iptype"])
            (d / "ia").write_text(ia)
            (d / "reg").write_text(str(item.get("reg", 1)))
            (d / "ia_set_noop").write_text(str(item.get("ia_set_noop", 0)))
            (d / "cops").write_text(item.get("cops", "0 43211"))
            (d / "cops_set_ok").write_text(str(item.get("cops_set_ok", 1)))
            (d / "cops_err_applied").write_text(str(item.get("cops_err_applied", 0)))
            (d / "cops_noop").write_text(str(item.get("cops_noop", 0)))
            (d / "nrcur").write_text(item.get("nrcur", "080800d5 000001a0 00003000"))
            (d / "nr_noop").write_text(str(item.get("nr_noop", 0)))
            if item.get("nr_getfail"):
                (d / "nr_getfail").write_text("1")
            if item.get("nr_missing"):
                (d / "nr_missing").write_text("1")
            (d / "epbse").write_text(item.get("epbse", "154,145,2282225877,1952,0,0,0,0,0,0"))
            (d / "epbse_noop").write_text(str(item.get("epbse_noop", 0)))
            (d / "lock").write_text(item.get("lock", "0"))
            (d / "lock_noop").write_text(str(item.get("lock_noop", 0)))
            (d / "act_hang").write_text(str(item.get("act_hang", 0)))
            (d / "cfun_ok").write_text(str(item.get("cfun_ok", 1)))
            (d / "get").write_text(json.dumps(item["get"]) if item.get("get") else "")
            for field in ["sim", "activate_rc", "deactivate_rc", "notify_rc", "link", "operation", "vendor_active", "status_rc"]:
                (d / field).write_text(str(item[field]))
        archive = tmp / "inputs.tgz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(script, arcname="package/x28-mipc/files/x28_mipc.sh")
            tar.add(ROOT / "tests/run-case.sh", arcname="tests/run-case.sh")
            tar.add(tmp / "cases", arcname="cases")
        run(ssh + ["mkdir -m 700 " + shlex.quote(stage)])
        try:
            run(["scp", "-O", "-q", str(archive), args.router + ":" + stage + "/inputs.tgz"])
            run(ssh + ["tar -xzf " + stage + "/inputs.tgz -C " + stage])
            for item in items:
                cmd = ["sh", stage + "/tests/run-case.sh", stage, stage + "/cases/" + item["name"]]
                result = run(ssh + [shlex.join(cmd)])
                assert not result.stderr or item["name"] == "malformed-json", result.stderr
            result_path = ROOT / ".test-results"
            result_path.mkdir(exist_ok=True)
            run(ssh + ["tar -czf " + stage + "/results.tgz -C " + stage + " cases"])
            run(["scp", "-O", "-q", args.router + ":" + stage + "/results.tgz", str(tmp / "results.tgz")])
            with tarfile.open(tmp / "results.tgz") as tar:
                for item in items:
                    directory = result_path / "cases" / item["name"]
                    directory.mkdir(parents=True, exist_ok=True)
                    for name in ["commands", "notifications", "exit_code"]:
                        data = tar.extractfile("cases/" + item["name"] + "/" + name)
                        assert data is not None, "Missing test result"
                        (directory / name).write_bytes(data.read())
                    for name, src in [("ip6del", "ip6del"), ("pinfo", "sysctl/ccmni7/accept_ra_pinfo"),
                                      ("accept_ra", "sysctl/ccmni7/accept_ra")]:
                        (directory / name).unlink(missing_ok=True)
                        if "cases/" + item["name"] + "/" + src in tar.getnames():
                            (directory / name).write_bytes(tar.extractfile("cases/" + item["name"] + "/" + src).read())
            for item in items:
                verify(item, result_path / "cases" / item["name"])
                print("PASS", item["name"])
        finally:
            run(ssh + ["rm -rf " + shlex.quote(stage)])
    print(f"{len(items)} native lifecycle cases passed; all modem and ubus commands were mocked.")

if __name__ == "__main__":
    main()
