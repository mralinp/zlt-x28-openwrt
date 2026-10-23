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

def case(name, *, config=None, reply=None, error=None, cleanup=False, **extra):
    return {"name": name, "config": {**CONFIG, **(config or {})},
            "reply": {**REPLY, **(reply or {})}, "error": error, "cleanup": cleanup,
            "sim": "MIPC_SIM_STATUS_COMPLETE_READY", "activate_rc": 0,
            "deactivate_rc": 0, "notify_rc": 0, "link": "up", "operation": "setup",
            "vendor_active": 0, "status_rc": 0, "status": {}, **extra}

def cases():
    own = {"data": {"x28_mipc_cid": 4, "x28_mipc_owner": "wan"}}
    return [
        case("point-to-point"),
        case("gateway", reply={"v4_gw": "198.51.100.1", "v4_mask": "255.255.255.0"}),
        case("no-route-dns", config={"defaultroute": False, "peerdns": False}),
        case("bad-apn", config={"apn": "x;touch /tmp/should-not-exist"}, error="INVALID_CONFIG", no_cli=True),
        case("bad-mtu", config={"mtu": 575}, error="INVALID_CONFIG", no_cli=True),
        case("ipv6-config", config={"iptype": 3}, error="IPV4_ONLY", no_cli=True),
        case("vendor-active", vendor_active=1, error="VENDOR_WAN_ACTIVE", no_cli=True),
        case("sim-locked", sim="MIPC_SIM_STATUS_SIM_PIN", error="SIM_PIN_LOCKED", no_activate=True),
        case("sim-pending", sim="MIPC_SIM_STATUS_NOT_READY", error="SIM_NOT_READY", no_activate=True),
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
        assert activation == {"apn": item["config"]["apn"], "ip_type": 1, "roaming_type": 3,
                              "auth_type": 0, "username": "", "password": "",
                              "bearer_bitmask": "0xfffdffff", "mtu": item["config"]["mtu"], "mode": 1}, activation
    deactivations = [c for c in commands if c.startswith("--data_call_deact ")]
    assert deactivations == (["--data_call_deact 4"] if item["cleanup"] else []), commands
    if item.get("no_cli"):
        assert not commands, commands
    if item.get("no_activate"):
        assert commands == ["--show_sim_status"], commands
    if item["error"]:
        assert rc != 0 and any(item["error"] in e.get("error", []) for e in errors), (rc, events)
        if item["error"] != "NOTIFY_FAILED":
            assert not up, events
    else:
        assert rc == 0 and not errors, (rc, events)
        if item["operation"] == "setup":
            assert len(up) == 1 and up[0]["interface"] == "wan" and up[0]["ifname"] == "ccmni7", events
            assert up[0]["ipaddr"] == [{"ipaddr": "198.51.100.7", "mask": "24" if item["name"] == "gateway" else "32"}], events
            assert up[0]["data"] == {"x28_mipc_cid": 4, "x28_mipc_owner": "wan"}, events
            if item["name"] == "no-route-dns":
                assert not up[0].get("routes") and not up[0].get("dns"), events
            else:
                assert up[0]["dns"] == ["192.0.2.53"], events
                route = up[0]["routes"][0]
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
            for item in items:
                verify(item, result_path / "cases" / item["name"])
                print("PASS", item["name"])
        finally:
            run(ssh + ["rm -rf " + shlex.quote(stage)])
    print(f"{len(items)} native lifecycle cases passed; all modem and ubus commands were mocked.")

if __name__ == "__main__":
    main()
