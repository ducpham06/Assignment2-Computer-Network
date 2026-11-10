#!/usr/bin/env python3
"""Render docs/eve-ng-build-guide.md (node list + full cabling table) from the SoT."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sot  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = {"vios": "Cisco vIOS (vios-adventerprisek9-m), 512 MB, **6 Ethernets**",
       "viosl2": "Cisco IOSvL2, 768 MB, 4 Ethernet groups (16 ports)",
       "veos": "Arista vEOS-lab, 2048 MB, 4+ Ethernets"}

L = ["# EVE-NG build guide", "",
     "Generated from `tools/sot.py` -- the cabling below is exactly what the configs expect.", "",
     "## 0. Host sizing (12 GB laptop)", "",
     f"* Give the EVE-NG VM **10 GB RAM** and 4+ vCPUs, enable nested virtualisation (VT-x/AMD-V).",
     f"* Lab A needs about {sum(sot.RAM_MB[d['platform']] for d in sot.DEVICES.values() if d['lab'] == 'A') / 1024:.1f} GB "
     "(UKSM/KSM in EVE-NG shares identical image pages, so real usage is lower). Run Lab B separately, "
     "with Lab A stopped (1 spine = 6 GB; add DC-SPINE2 only if you have the RAM).",
     "* Start nodes in this order and wait for each group to boot: ISPs -> edges -> cores -> access -> server -> VPCS.", "",
     "## 1. Images", "",
     "| Template | Settings |", "|---|---|"]
for k, v in TPL.items():
    L.append(f"| {k} | {v} |")
L += ["| VPCS | built-in |", "",
      "## 2. Management network", "",
      "1. Add a **Network** object of type *Management(Cloud0)*.",
      "2. Connect **Gi0/0** of every Cisco node (Management1 on vEOS) to it.",
      "3. On the EVE-NG VM shell: `ip addr add 172.16.99.1/24 dev pnet0` (add it to `/etc/network/interfaces` to keep it after reboot).",
      "4. Test from the EVE VM: `ping 172.16.99.11` once HCM-EDG1 is configured.", "",
      "## 3. Nodes (Lab A)", "", "| Node | Template | Role | OOB mgmt |", "|---|---|---|---|"]
for n, d in sot.DEVICES.items():
    if d["lab"] == "A":
        L.append(f"| {n} | {d['platform']} | {d['role']} | {d['mgmt']} |")
for sw, pif, ep, epif, data, voice in sot.ACCESS_PORTS:
    if ep.startswith("PC-"):
        L.append(f"| {ep} | VPCS | host VLAN {data} | -- |")
L += ["", "## 4. Cabling (Lab A)", "", "| # | From | Port | To | Port | Purpose |", "|---|---|---|---|---|---|"]
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
L += ["", f"Plus Gi0/0 of all {len(sot.lab_a_devices())} Cisco nodes to Cloud0.", "",
      "## 5. Configure", "",
      "1. Console into each node, `enable`, `configure terminal`, paste `configs/labA/<NODE>.cfg`, then `end` and `write memory`.",
      "   * IOSvL2 may print `%Warning` lines for features it ignores; check for `% Invalid input` and report them.",
      "   * The RSA key line takes a few seconds -- wait for the prompt before the rest of the paste continues.",
      "2. On each VPCS, paste `configs/vpcs/<NODE>.vpc` (DHCP + SLAAC) and `save`.",
      "3. Wait ~60 s, then run the checks in `docs/test-plan.md`.", "",
      "## 6. Lab B (EVPN-VXLAN)", "",
      "| # | From | Port | To | Port |", "|---|---|---|---|---|"]
for k, (s, si, l, li, net) in enumerate(sot.DC["fabric_links"], 1):
    L.append(f"| {k} | {s} | {si} | {l} | {li} ({net}) |")
for lf, li, h, vlan, hip in sot.DC["hosts"]:
    L.append(f"| - | {lf} | {li} | {h} (VPCS) | eth0, VLAN {vlan} |")
L += ["", "Paste `configs/labB/*.cfg`, `write`, then `reload` each vEOS once (multi-agent routing model). "
      "If you run only one spine, simply do not create DC-SPINE2: the leaf sessions to 10.10.191.2 stay idle.", "",
      "Verify: `show bgp evpn summary`, `show vxlan vtep`, `show bgp evpn route-type mac-ip`, then ping DC-H1 -> DC-H2 (L2VNI) and DC-H1 -> DC-H3 (L3VNI).", ""]
open(os.path.join(ROOT, "docs", "eve-ng-build-guide.md"), "w").write("\n".join(L))
print("wrote docs/eve-ng-build-guide.md")
