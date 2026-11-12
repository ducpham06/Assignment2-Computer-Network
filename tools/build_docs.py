#!/usr/bin/env python3
"""Render docs/eve-ng-build-guide.md (node list + full cabling table) from the SoT."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sot  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = {"vios": "Cisco vIOS `vios-adventerprisek9-m.SPA.159-3.M6` (extract the `.tgz` into `/opt/unetlab/addons/qemu/`), 512 MB, **6 Ethernets**",
       "viosl2": "Cisco vIOS-L2 `viosl2-adventerprisek9-m.ssa.high_iron_20200929` (extract the `.tgz` the same way), 1024 MB, 4 Ethernet groups (16 ports)",
}

L = ["# EVE-NG build guide", "",
     "Generated from `tools/sot.py` -- the cabling below is exactly what the configs expect.", "",
     "## 0. Host sizing", "",
     "Reference host: Intel Core Ultra 5 125H (14 cores / 18 threads), 32 GB RAM.", "",
     "* The team's EVE-NG VM: **17.5 GB RAM** and **8 vCPUs** (any VM with 16 GB or more works); enable *Virtualize Intel VT-x/EPT* (nested virtualisation).",
     f"* The whole topology (campus/WAN + DC fabric) needs about {sum(sot.RAM_MB[d['platform']] for d in sot.DEVICES.values()) / 1024:.1f} GB "
     "of node RAM, so everything runs in **one** EVE-NG lab at the same time.",
     "* Plug the laptop into mains power and use the *Performance* power mode during the demo (the hybrid P/E cores throttle on battery).",
     "* Start nodes in batches of 3-5: ISPs -> edges -> cores -> access -> server -> spines -> leaves -> VPCS.", "",
     "## 1. Images", "",
     "| Template | Settings |", "|---|---|"]
for k, v in TPL.items():
    L.append(f"| {k} | {v} |")
L += ["| VPCS | built-in |", "",
      "## 2. Management network", "",
      "1. Add a **Network** object of type *Management(Cloud0)*.",
      "2. Connect **Gi0/0** of every node to it.",
      "3. On the EVE-NG VM shell: `ip addr add 172.16.99.1/24 dev pnet0` (add it to `/etc/network/interfaces` to keep it after reboot).",
      "4. Test from the EVE VM: `ping 172.16.99.11` once HCM-EDG1 is configured.", "",
      "## 3. Nodes", "", "| Node | Template | Role | OOB mgmt |", "|---|---|---|---|"]
for n, d in sot.DEVICES.items():
    L.append(f"| {n} | {d['platform']} | {d['role']} | {d['mgmt']} |")
for sw, pif, ep, epif, data, voice in sot.ACCESS_PORTS:
    if ep.startswith("PC-"):
        L.append(f"| {ep} | VPCS | host VLAN {data} | -- |")
for lf, li, h, vrf, net, hip in sot.DC["hosts"]:
    L.append(f"| {h} | VPCS | DC host, {vrf} | -- |")
L += ["", "## 4. Cabling", "", "| # | From | Port | To | Port | Purpose |", "|---|---|---|---|---|---|"]
i = 0
def row(a, ai, b, bi, why):
    global i
    i += 1
    L.append(f"| {i} | {a} | {ai} | {b} | {bi} | {why} |")
for isp, iif, ce, cif, net in sot.ISP_LINKS:
    row(isp, iif, ce, cif, f"carrier access {net}")
a, ai, b, bi, net = sot.ISP_PEERING
row(a, ai, b, bi, f"ISP peering {net}")
for site, a, ai, b, bi, v4, v6 in sot.P2P_LINKS:
    if not ai.startswith("Vlan"):
        row(a, ai, b, bi, f"routed {v4}")
for a, ai, b, bi, po in sot.TRUNKS:
    row(a, ai, b, bi, f"802.1Q trunk{' (Po1 LACP member)' if po else ''}")
for sw, pif, ep, epif, data, voice in sot.ACCESS_PORTS:
    row(sw, pif, ep, epif, f"access VLAN {data}")
for core, cif, lf, lif, net in sot.BORDER_LINKS:
    row(core, cif, lf, lif, f"DC border {net}")
for s_, si, lf, li, net in sot.DC["fabric_links"]:
    row(s_, si, lf, li, f"fabric {net}")
for lf, li, h, vrf, net, hip in sot.DC["hosts"]:
    row(lf, li, h, "eth0", f"DC host {vrf} {net}")
L += ["", f"Plus Gi0/0 of all {len(sot.DEVICES)} Cisco nodes to Cloud0.", "",
      "## 5. Configure", "",
      "1. Console into each node, `enable`, `configure terminal`, paste `configs/labA/<NODE>.cfg`, then `end` and `write memory`.",
      "   * IOSvL2 may print `%Warning` lines for features it ignores; check for `% Invalid input` and report them.",
      "   * The RSA key line takes a few seconds -- wait for the prompt before the rest of the paste continues.",
      "2. DC fabric nodes are vIOS too: paste `configs/labB/<NODE>.cfg` the same way.",
      "3. On each VPCS, paste `configs/vpcs/<NODE>.vpc` and `save`.",
      "4. Wait ~60 s, then run the checks in `docs/test-plan.md`.", "",
      "## 6. DC fabric checks", "",
      "`show mpls ldp neighbor`, `show bgp vpnv4 unicast all summary`, `show ip route vrf TENANT-PROD` on the leaves; "
      "ping DC-H1 -> DC-H2 (PROD across the fabric), DC-H3 -> DC-H4 (DEV), DC-H1 -> DC-H3 (must FAIL: tenant isolation) "
      "and DC-H1 -> PC-HAN-ENG (border + WAN overlay). "
      "On HCM-CORE1: `show ip route ospf | i 10.10.12` shows the DC tenant subnets learned from the leaves.", ""]
open(os.path.join(ROOT, "docs", "eve-ng-build-guide.md"), "w").write("\n".join(L))
print("wrote docs/eve-ng-build-guide.md")
