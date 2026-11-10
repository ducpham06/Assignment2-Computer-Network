#!/usr/bin/env python3
"""
tvi_auto.py -- TVI network automation (Step 9)
==============================================

Tasks (choose with --task, default "all" = backup -> provision -> backup -> verify):

  backup      show running-config + show ip interface brief from every selected node,
              saved as backups/<hostname>_<timestamp>_backup.cfg (+ _ipbrief.txt)
  provision   push the Day-1 baseline (AAA, NTP, syslog, banner, login hardening) to every
              managed node and create/rename the corporate VLANs on core/access switches,
              using the payload in vars/; then 'write memory'
  verify      compliance check: every VLAN in the payload exists with the right name
  telemetry   collect protocol state (OSPF, BGP, HSRP, LACP, STP, tunnels) into telemetry/*.json
  all         pre-backup, provision, post-backup, pre/post diff, verify

Credentials are NEVER stored in this file or in the inventory:
  * environment variables TVI_SSH_USER / TVI_SSH_PASS (/ TVI_ENABLE_SECRET), or
  * an interactive prompt (input + getpass) when the variables are absent.

Examples
  python3 tvi_auto.py --dry-run                         # show what would be pushed, no SSH
  python3 tvi_auto.py --task backup                     # snapshot every node
  python3 tvi_auto.py --task provision --site HAN       # one site only
  python3 tvi_auto.py --task all --role core access     # switches only
  python3 tvi_auto.py --task telemetry
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import difflib
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from getpass import getpass

import yaml

try:
    from netmiko import ConnectHandler
    from netmiko.exceptions import (ConfigInvalidException, NetmikoAuthenticationException,
                                    NetmikoTimeoutException)
except ImportError:  # allows --dry-run / tests on a machine without netmiko
    ConnectHandler = None

    class NetmikoTimeoutException(Exception):
        pass

    class NetmikoAuthenticationException(Exception):
        pass

    class ConfigInvalidException(Exception):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(HERE, "backups")
LOG_DIR = os.path.join(HERE, "logs")
TELEMETRY_DIR = os.path.join(HERE, "telemetry")
LOG_FILE = os.path.join(LOG_DIR, "automation.log")
SWITCH_ROLES = {"core", "access"}
ERROR_PATTERN = r"% ?(Invalid input|Incomplete command|Ambiguous command|Unknown command)"

log = logging.getLogger("tvi")


# --------------------------------------------------------------------------- data
@dataclass
class Device:
    hostname: str
    host: str
    device_type: str
    site: str
    role: str
    port: int = 22
    managed: bool = True
    lab: str = "A"


@dataclass
class Result:
    hostname: str
    ok: bool = True
    steps: list = field(default_factory=list)
    files: list = field(default_factory=list)
    error: str = ""
    compliance: dict = field(default_factory=dict)
    telemetry: dict = field(default_factory=dict)


def setup_logging(verbose: bool = False) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    log.setLevel(logging.DEBUG)
    log.handlers.clear()
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(threadName)s - %(message)s"))
    fh.setLevel(logging.INFO)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(message)s"))
    sh.setLevel(logging.DEBUG if verbose else logging.INFO)
    log.addHandler(fh)
    log.addHandler(sh)


def load_inventory(path: str) -> list[Device]:
    with open(path) as f:
        data = yaml.safe_load(f)
    defaults = data.get("defaults", {})
    out = []
    for d in data["devices"]:
        merged = {**defaults, **d}
        out.append(Device(hostname=merged["hostname"], host=merged["ip"], device_type=merged["device_type"],
                          site=merged["site"], role=merged["role"], port=int(merged.get("port", 22)),
                          managed=bool(merged.get("managed", True)), lab=str(merged.get("lab", "A"))))
    return out


def load_vars(vars_dir: str) -> tuple[dict, dict]:
    with open(os.path.join(vars_dir, "baseline.yaml")) as f:
        baseline = yaml.safe_load(f)
    with open(os.path.join(vars_dir, "vlans.yaml")) as f:
        vlans = yaml.safe_load(f)
    return baseline, vlans


def get_credentials() -> dict:
    """Environment variables first, interactive prompt otherwise. Never logged."""
    user = os.environ.get("TVI_SSH_USER") or input("SSH username: ")
    pwd = os.environ.get("TVI_SSH_PASS") or getpass("SSH password: ")
    secret = os.environ.get("TVI_ENABLE_SECRET", pwd)
    return {"username": user, "password": pwd, "secret": secret}


# --------------------------------------------------------------------------- payload
def vlan_payload(dev: Device, vlans: dict) -> list[dict]:
    """Standard enterprise VLANs + any site-specific additions for this device's site."""
    items = {v["id"]: v["name"] for v in vlans.get("standard_vlans", [])}
    for v in (vlans.get("site_vlans") or {}).get(dev.site, []) or []:
        items[v["id"]] = v["name"]
    return [{"id": k, "name": items[k]} for k in sorted(items)]


def build_commands(dev: Device, baseline: dict, vlans: dict) -> list[str]:
    if dev.device_type != "cisco_ios":
        return []                          # Lab B (EOS) is backup/telemetry only
    cmds: list[str] = []
    cmds += baseline.get("aaa", [])
    if dev.role not in baseline.get("ntp_exclude_roles", []):
        cmds += [f"ntp server {s}" for s in baseline.get("ntp_servers", [])]
    cmds += [f"logging host {h}" for h in baseline.get("syslog_hosts", [])]
    cmds += baseline.get("logging", [])
    cmds += baseline.get("hardening", [])
    banner = " ".join(baseline.get("banner", "").split())
    if banner:
        cmds.append(f"banner motd ^{banner}^")
    if dev.role in SWITCH_ROLES:
        for v in vlan_payload(dev, vlans):
            cmds += [f"vlan {v['id']}", f"name {v['name']}", "exit"]
    return cmds


# --------------------------------------------------------------------------- helpers
def ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_text(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    return path


def strip_volatile(cfg: str) -> list[str]:
    """Drop lines that change on every capture so the diff only shows real changes."""
    skip = re.compile(r"^(Building configuration|Current configuration|! Last configuration change|"
                      r"! NVRAM config last updated|ntp clock-period)")
    return [l for l in cfg.splitlines() if not skip.match(l)]


def parse_vlans(show_vlan_brief: str) -> dict[int, str]:
    out = {}
    for line in show_vlan_brief.splitlines():
        m = re.match(r"^(\d+)\s+(\S+)\s+(active|act/lshut|sus|act/unsup)", line)
        if m:
            out[int(m.group(1))] = m.group(2)
    return out


def count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, flags=re.M))


# --------------------------------------------------------------------------- per-device work
def capture(conn, dev: Device, res: Result, stage: str) -> str:
    stamp = ts()
    while os.path.exists(os.path.join(BACKUP_DIR, f"{dev.hostname}_{stamp}_backup.cfg")):
        time.sleep(1)                      # pre and post in the same second: keep both files
        stamp = ts()
    run = conn.send_command("show running-config", read_timeout=60)
    brief = conn.send_command("show ip interface brief")
    cfg_path = save_text(os.path.join(BACKUP_DIR, f"{dev.hostname}_{stamp}_backup.cfg"),
                         f"! TVI backup  host={dev.hostname}  stage={stage}  time={stamp}\n{run}\n")
    br_path = save_text(os.path.join(BACKUP_DIR, f"{dev.hostname}_{stamp}_ipbrief.txt"), brief + "\n")
    res.files += [cfg_path, br_path]
    res.steps.append(f"{stage}-backup")
    log.info(f"[{dev.hostname}] {stage}-change backup -> {os.path.relpath(cfg_path, HERE)}")
    return run


def verify_vlans(conn, dev: Device, vlans: dict, res: Result) -> None:
    if dev.role not in SWITCH_ROLES or dev.device_type != "cisco_ios":
        return
    have = parse_vlans(conn.send_command("show vlan brief"))
    missing, wrong = [], []
    for v in vlan_payload(dev, vlans):
        if v["id"] not in have:
            missing.append(v["id"])
        elif have[v["id"]] != v["name"]:
            wrong.append(f"{v['id']}:{have[v['id']]}!={v['name']}")
    res.compliance = {"missing": missing, "wrong_name": wrong, "ok": not missing and not wrong}
    if res.compliance["ok"]:
        log.info(f"[{dev.hostname}] compliance PASS ({len(vlan_payload(dev, vlans))} VLANs)")
    else:
        res.ok = False
        log.error(f"[{dev.hostname}] compliance FAIL missing={missing} wrong={wrong}")
    res.steps.append("verify")


TELEMETRY_CMDS = {
    "ospf": "show ip ospf neighbor",
    "bgp": "show bgp ipv4 unicast summary",
    "hsrp": "show standby brief",
    "lacp": "show etherchannel summary",
    "stp": "show spanning-tree summary",
    "tunnels": "show interfaces description | include Tu",
    "ipsec": "show crypto ikev2 sa",
}
ROLE_TELEMETRY = {
    "edge": ["ospf", "bgp", "tunnels", "ipsec"] ,
    "core": ["ospf", "hsrp", "lacp", "stp"],
    "access": ["stp"],
    "isp": ["bgp"],
    "server": [],
}


def collect_telemetry(conn, dev: Device, res: Result) -> None:
    keys = ROLE_TELEMETRY.get(dev.role, [])
    if dev.site in ("HAN", "DAD") and dev.role == "edge":
        keys = keys + ["hsrp"]
    raw = {k: conn.send_command(TELEMETRY_CMDS[k]) for k in keys}
    summary = {}
    if "ospf" in raw:
        summary["ospf_full"] = count(r"\bFULL/", raw["ospf"])
    if "bgp" in raw:
        # established peers show a number (prefixes received) in the last column
        summary["bgp_established"] = count(r"^\S+\s+4\s+\d+(?:\s+\S+){6}\s+\d+\s*$", raw["bgp"])
        summary["bgp_down"] = count(r"^\S+\s+4\s+\d+(?:\s+\S+){6}\s+(Idle|Active|Connect)", raw["bgp"])
    if "hsrp" in raw:
        summary["hsrp_active"] = count(r"\bActive\b", raw["hsrp"])
        summary["hsrp_standby"] = count(r"\bStandby\b", raw["hsrp"])
    if "lacp" in raw:
        summary["po_bundled_members"] = count(r"\(P\)", raw["lacp"])
    if "tunnels" in raw:
        summary["tunnels_up"] = count(r"^Tu\d+\s+up\s+up", raw["tunnels"])
    if "ipsec" in raw:
        summary["ikev2_ready"] = count(r"\bREADY\b", raw["ipsec"])
    res.telemetry = {"summary": summary, "raw": raw}
    res.steps.append("telemetry")
    log.info(f"[{dev.hostname}] telemetry {summary}")


def work(dev: Device, task: str, creds: dict, baseline: dict, vlans: dict, timeout: int) -> Result:
    res = Result(dev.hostname)
    params = {"device_type": dev.device_type, "host": dev.host, "port": dev.port,
              "username": creds["username"], "password": creds["password"], "secret": creds["secret"],
              "timeout": timeout, "conn_timeout": timeout, "fast_cli": False}
    log.info(f"[{dev.hostname}] connecting to {dev.host}:{dev.port} ({dev.device_type})")
    conn = None
    try:
        conn = ConnectHandler(**params)
        if dev.device_type == "cisco_ios":
            conn.enable()
        if task in ("backup", "all"):
            pre = capture(conn, dev, res, "pre")
        if task in ("provision", "all") and dev.managed:
            cmds = build_commands(dev, baseline, vlans)
            if cmds:
                out = conn.send_config_set(cmds, error_pattern=ERROR_PATTERN, read_timeout=60)
                log.debug(out)
                log.info(f"[{dev.hostname}] pushed {len(cmds)} config lines")
                conn.save_config()
                log.info(f"[{dev.hostname}] write memory OK")
                res.steps.append("provision")
        if task == "all":
            post = capture(conn, dev, res, "post")
            diff = "\n".join(difflib.unified_diff(strip_volatile(pre), strip_volatile(post),
                                                  "pre-change", "post-change", lineterm=""))
            p = save_text(os.path.join(BACKUP_DIR, f"{dev.hostname}_{ts()}_diff.txt"), diff or "(no change)\n")
            res.files.append(p)
            n = sum(1 for l in diff.splitlines() if l[:1] in "+-" and l[:3] not in ("+++", "---"))
            log.info(f"[{dev.hostname}] config diff: {n} changed lines -> {os.path.relpath(p, HERE)}")
        if task in ("verify", "all"):
            verify_vlans(conn, dev, vlans, res)
        if task == "telemetry":
            collect_telemetry(conn, dev, res)
    except NetmikoTimeoutException as e:
        res.ok, res.error = False, f"connection timed out ({dev.host})"
        log.error(f"[{dev.hostname}] {res.error}: {e}")
    except NetmikoAuthenticationException:
        res.ok, res.error = False, "authentication failed"
        log.error(f"[{dev.hostname}] {res.error} for user '{creds['username']}'")
    except ConfigInvalidException as e:
        res.ok, res.error = False, "device rejected a command"
        log.error(f"[{dev.hostname}] {res.error}: {e}")
    except Exception as e:  # noqa: BLE001 -- log anything unexpected and keep going
        res.ok, res.error = False, f"{type(e).__name__}: {e}"
        log.exception(f"[{dev.hostname}] unexpected error")
    finally:
        if conn:
            try:
                conn.disconnect()
            except Exception:  # noqa: BLE001
                pass
    if res.ok:
        log.info(f"[{dev.hostname}] SUCCESS ({', '.join(res.steps) or 'nothing to do'})")
    return res


# --------------------------------------------------------------------------- main
def select(devs: list[Device], args) -> list[Device]:
    out = [d for d in devs if d.lab in args.lab]
    if args.site:
        out = [d for d in out if d.site in args.site]
    if args.role:
        out = [d for d in out if d.role in args.role]
    if args.hosts:
        out = [d for d in out if d.hostname in args.hosts]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="TVI baseline/VLAN provisioning, backup and telemetry")
    ap.add_argument("--task", choices=["backup", "provision", "verify", "telemetry", "all"], default="all")
    ap.add_argument("--inventory", default=os.path.join(HERE, "inventory.yaml"))
    ap.add_argument("--vars", default=os.path.join(HERE, "vars"))
    ap.add_argument("--site", nargs="*", help="HCM HAN DAD WAN")
    ap.add_argument("--role", nargs="*", help="edge core access server isp spine leaf")
    ap.add_argument("--hosts", nargs="*", help="explicit hostnames")
    ap.add_argument("--lab", nargs="*", default=["A"], help="A (campus/WAN, default) and/or B (DC fabric)")
    ap.add_argument("--workers", type=int, default=4, help="parallel SSH sessions")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true", help="print the payload per device, no SSH")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    setup_logging(args.verbose)
    devs = select(load_inventory(args.inventory), args)
    baseline, vlans = load_vars(args.vars)
    if not devs:
        log.error("no device matches the filters")
        return 2
    log.info(f"=== TVI automation: task={args.task} devices={len(devs)} dry_run={args.dry_run} ===")

    if args.dry_run:
        for d in devs:
            cmds = build_commands(d, baseline, vlans) if d.managed else []
            print(f"\n### {d.hostname} ({d.host}, {d.role}, {d.site}) -- {len(cmds)} lines")
            for c in cmds:
                print("   " + c)
        log.info("dry-run complete, nothing was sent")
        return 0

    if ConnectHandler is None:
        log.error("netmiko is not installed: pip install -r requirements.txt")
        return 2
    creds = get_credentials()
    results: list[Result] = []
    with cf.ThreadPoolExecutor(max_workers=args.workers, thread_name_prefix="ssh") as ex:
        futs = [ex.submit(work, d, args.task, creds, baseline, vlans, args.timeout) for d in devs]
        for f in cf.as_completed(futs):
            results.append(f.result())

    results.sort(key=lambda r: r.hostname)
    if args.task == "telemetry":
        os.makedirs(TELEMETRY_DIR, exist_ok=True)
        p = os.path.join(TELEMETRY_DIR, f"telemetry_{ts()}.json")
        json.dump({r.hostname: r.telemetry for r in results}, open(p, "w"), indent=2)
        log.info(f"telemetry saved -> {os.path.relpath(p, HERE)}")

    print("\n" + "-" * 78)
    print(f"{'Device':<12} {'Result':<7} {'Steps':<34} Detail")
    print("-" * 78)
    for r in results:
        detail = r.error or (("compliance " + ("PASS" if r.compliance.get("ok") else "FAIL")) if r.compliance else "")
        if r.telemetry:
            detail = json.dumps(r.telemetry["summary"])
        print(f"{r.hostname:<12} {'OK' if r.ok else 'FAIL':<7} {','.join(r.steps):<34} {detail}")
    failed = [r for r in results if not r.ok]
    log.info(f"=== finished: {len(results) - len(failed)} ok, {len(failed)} failed (log: logs/automation.log) ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
