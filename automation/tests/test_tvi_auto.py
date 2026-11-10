"""
Offline tests for tvi_auto.py: a fake Netmiko connection stands in for the
devices so the whole workflow (backup -> push -> save -> backup -> diff ->
verify, plus error handling) runs without EVE-NG.

    cd automation && python3 -m pytest -q
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import tvi_auto as ta  # noqa: E402

VLAN_BEFORE = """VLAN Name                             Status    Ports
---- -------------------------------- --------- -------------------------------
1    default                          active
10   EXEC_FINANCE                     active    Gi1/0
99   MANAGEMENT                       active
"""


class FakeConn:
    """Minimal stand-in for a Netmiko connection with a mutable VLAN table."""
    def __init__(self, **kw):
        self.kw = kw
        self.vlans = {1: "default", 10: "EXEC_FINANCE", 99: "MANAGEMENT"}
        self.cfg = ["hostname X", "interface Gi0/0"]
        self.saved = False

    def enable(self):
        pass

    def send_command(self, cmd, **kw):
        if cmd == "show running-config":
            return "Building configuration...\n" + "\n".join(self.cfg)
        if cmd == "show ip interface brief":
            return "Interface  IP-Address  OK? Method Status Protocol"
        if cmd == "show vlan brief":
            return "\n".join(f"{k:<4} {v:<32} active" for k, v in sorted(self.vlans.items()))
        return ""

    def send_config_set(self, cmds, **kw):
        cur = None
        for c in cmds:
            if c.startswith("vlan "):
                cur = int(c.split()[1])
                self.vlans.setdefault(cur, f"VLAN{cur:04d}")
            elif c.startswith("name ") and cur:
                self.vlans[cur] = c.split()[1]
            self.cfg.append(c)
        return "\n".join(cmds)

    def save_config(self):
        self.saved = True

    def disconnect(self):
        pass


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(ta, "BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(ta, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(ta, "LOG_FILE", str(tmp_path / "logs" / "automation.log"))
    monkeypatch.setattr(ta, "TELEMETRY_DIR", str(tmp_path / "telemetry"))
    ta.setup_logging()
    yield tmp_path


def inv():
    return ta.load_inventory(os.path.join(os.path.dirname(HERE), "inventory.yaml"))


def payload():
    return ta.load_vars(os.path.join(os.path.dirname(HERE), "vars"))


CREDS = {"username": "u", "password": "S3cr3t-Should-Not-Leak", "secret": "S3cr3t-Should-Not-Leak"}


def test_inventory_has_no_credentials():
    text = open(os.path.join(os.path.dirname(HERE), "inventory.yaml")).read().lower()
    assert "password" not in text.replace("tvi_ssh_pass", "") and "secret" not in text


def test_script_has_no_plaintext_password():
    src = open(os.path.join(os.path.dirname(HERE), "tvi_auto.py")).read()
    assert "Tvi@Lab2026" not in src


def test_switch_gets_vlans_router_does_not():
    baseline, vlans = payload()
    d = {x.hostname: x for x in inv()}
    sw = ta.build_commands(d["HCM-ACC1"], baseline, vlans)
    rt = ta.build_commands(d["HCM-EDG1"], baseline, vlans)
    for v in ("vlan 10", "name EXEC_FINANCE", "vlan 20", "name RND_ENGINEERING", "vlan 30", "vlan 99"):
        assert v in sw
    assert not any(c.startswith("vlan ") for c in rt)
    assert "ntp server 10.10.43.10" in rt and any(c.startswith("banner motd") for c in rt)
    assert "ntp server 10.10.43.10" not in ta.build_commands(d["HCM-SRV1"], baseline, vlans)


def test_site_vlans_are_merged():
    baseline, vlans = payload()
    vlans = {**vlans, "site_vlans": {"HAN": [{"id": 25, "name": "AI_TRAINING"}]}}
    d = {x.hostname: x for x in inv()}
    assert {"id": 25, "name": "AI_TRAINING"} in ta.vlan_payload(d["HAN-ACC1"], vlans)
    assert {"id": 25, "name": "AI_TRAINING"} not in ta.vlan_payload(d["DAD-ACC1"], vlans)


def test_full_workflow_backup_push_diff_verify(monkeypatch, isolate):
    conns = []
    monkeypatch.setattr(ta, "ConnectHandler", lambda **kw: conns.append(FakeConn(**kw)) or conns[-1])
    baseline, vlans = payload()
    dev = [x for x in inv() if x.hostname == "HAN-ACC1"][0]
    r = ta.work(dev, "all", CREDS, baseline, vlans, 5)
    assert r.ok, r.error
    assert r.steps == ["pre-backup", "provision", "post-backup", "verify"]
    assert r.compliance["ok"]
    assert conns[0].saved
    names = os.listdir(isolate / "backups")
    assert sum(n.endswith("_backup.cfg") for n in names) == 2
    assert any(n.endswith("_ipbrief.txt") for n in names)
    diff = [n for n in names if n.endswith("_diff.txt")][0]
    assert "+name RND_ENGINEERING" in open(isolate / "backups" / diff).read()
    log = open(isolate / "logs" / "automation.log").read()
    assert "SUCCESS" in log and "S3cr3t-Should-Not-Leak" not in log


def test_timeout_and_auth_errors_are_logged(monkeypatch, isolate):
    baseline, vlans = payload()
    dev = inv()[2]

    def boom_timeout(**kw):
        raise ta.NetmikoTimeoutException("TCP connection to device failed")

    def boom_auth(**kw):
        raise ta.NetmikoAuthenticationException("bad")

    monkeypatch.setattr(ta, "ConnectHandler", boom_timeout)
    assert not ta.work(dev, "backup", CREDS, baseline, vlans, 1).ok
    monkeypatch.setattr(ta, "ConnectHandler", boom_auth)
    r = ta.work(dev, "backup", CREDS, baseline, vlans, 1)
    assert r.error == "authentication failed"
    log = open(isolate / "logs" / "automation.log").read()
    assert "connection timed out" in log and "authentication failed" in log


def test_compliance_detects_wrong_name(monkeypatch):
    baseline, vlans = payload()
    dev = [x for x in inv() if x.hostname == "DAD-ACC1"][0]
    c = FakeConn()
    c.vlans[20] = "WRONG"
    r = ta.Result(dev.hostname)
    ta.verify_vlans(c, dev, vlans, r)
    assert not r.compliance["ok"] and r.compliance["missing"] == [30]


def test_dry_run_needs_no_network(capsys):
    assert ta.main(["--dry-run", "--site", "HCM"]) == 0
    out = capsys.readouterr().out
    assert "HCM-CORE1" in out and "name LOGISTICS_OPS" in out
