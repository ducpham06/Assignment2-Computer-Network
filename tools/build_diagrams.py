#!/usr/bin/env python3
"""Build all topology diagrams (SVG + PDF for the report, .drawio for editing)."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sot  # noqa: E402
from diagram_engine import Scene  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "diagrams")
os.makedirs(OUT, exist_ok=True)
A_COL, B_COL = "#1f77b4", "#d9711c"     # transport A / B
GRN, RED, GRY = "#2e8540", "#c0392b", "#6b7785"


def ifs(dev, short):
    return short


def p2p(dev_a, dev_b):
    for site, a, aif, b, bif, v4, v6 in sot.P2P_LINKS:
        if (a, b) == (dev_a, dev_b):
            return aif, bif, v4
    raise KeyError((dev_a, dev_b))


def isp(ce):
    for i, iif, c, cif, net in sot.ISP_LINKS:
        if c == ce:
            return i, iif, cif, net


# =========================================================================== 1. logical
def logical():
    s = Scene(1600, 930)
    s.text(800, 30, "TVI Innovations -- enterprise logical architecture (target design)", 17, "#1f2d3d", True, "middle")
    s.node("INET", "cloud", 800, 110, "Internet / SaaS", ["Microsoft 365, cloud IoT hub,", "public DNS"], size=(220, 100))
    s.node("SASE", "cloud", 1330, 120, "SASE / ZTNA PoP", ["identity-aware proxy, SWG,", "CASB, FWaaS"], size=(220, 100))
    s.node("REMOTE", "user", 1515, 230, "Remote workforce", ["ZTNA client + MFA"], label_pos="below")
    s.link("REMOTE", "SASE", GRN, 1.6, "5 3", mid="TLS / ZTNA")
    s.link("SASE", "INET", GRY, 1.4)
    s.node("ISPA", "cloud", 470, 265, "ISP-A  (AS 65100)", ["Broadband Internet", "Transport A"], size=(220, 95))
    s.node("ISPB", "cloud", 1130, 265, "ISP-B  (AS 65200)", ["MPLS / business fibre", "Transport B"], size=(220, 95))
    s.link("ISPA", "INET", GRY, 1.4)
    s.link("ISPB", "INET", GRY, 1.4)
    s.link("ISPA", "ISPB", GRY, 1.2, "3 3", mid="peering")
    # sites
    s.group(30, 360, 430, 400, "Hanoi R&D Campus  (AS 65020)", "#eef7ea", "#7fb069", sub="1,500 users -> 3,500 | 10.20.0.0/16 | 2001:db8:a020::/48")
    s.group(490, 360, 620, 540, "Ho Chi Minh City HQ  (AS 65010)", "#eef4fb", "#7a9cc6", sub="2,000 users -> 5,000 | 10.10.0.0/16 | 2001:db8:a010::/48 | data centre")
    s.group(1140, 360, 430, 400, "Da Nang Logistics Hub  (AS 65030)", "#fdf1e7", "#e0a46c", sub="500 users + 10k IoT | 10.30.0.0/16 | 2001:db8:a030::/48")
    for site, x0 in (("HAN", 30), ("HCM", 490), ("DAD", 1140)):
        span = 620 if site == "HCM" else 430
        e1x, e2x = x0 + span * 0.28, x0 + span * 0.72
        s.node(f"{site}-E1", "router", e1x, 440, f"{site}-EDG1", ["NGFW (ZBF) + SD-WAN"])
        s.node(f"{site}-E2", "router", e2x, 440, f"{site}-EDG2", ["NGFW (ZBF) + SD-WAN"])
        s.link(f"{site}-E1", f"{site}-E2", GRY, 1.4)
        s.link(f"{site}-E1", "ISPA", A_COL, 2.2, mid="DEMARC" if site == "HAN" else None)
        s.link(f"{site}-E2", "ISPB", B_COL, 2.2, mid="DEMARC" if site == "DAD" else None)
    # HCM interior
    s.node("HC1", "l3switch", 630, 570, "CORE1", ["L3 + HSRP"])
    s.node("HC2", "l3switch", 970, 570, "CORE2", ["L3 + HSRP"])
    s.link("HC1", "HC2", GRY, 2, double=True, mid="LACP")
    for e in ("HCM-E1", "HCM-E2"):
        for c in ("HC1", "HC2"):
            s.link(e, c, GRY, 1.4)
    s.node("HACC", "l2switch", 630, 700, "Access", ["802.1X, DHCP snooping, DAI"])
    s.link("HACC", "HC1", GRY, 1.3)
    s.link("HACC", "HC2", GRY, 1.3)
    s.node("HAP", "ap", 545, 800, "Wi-Fi 6 APs", ["CAPWAP -> WLC"])
    s.node("HEX", "user", 640, 810, "Executives", ["VLAN 10"])
    s.node("HWLC", "server", 735, 800, "WLC / DHCP", ["DNS / NTP"])
    for n in ("HAP", "HEX", "HWLC"):
        s.link(n, "HACC", GRY, 1)
    s.group(810, 640, 285, 240, "DC fabric: spine-leaf", "#ffffff", "#7a9cc6", dashed=False, sub="OSPF underlay, BGP overlay, tenant VRFs")
    s.node("SP1", "l3switch", 885, 705, "Spine1", size=(38, 32))
    s.node("SP2", "l3switch", 1020, 705, "Spine2", size=(38, 32))
    s.node("LF1", "l3switch", 885, 800, "Leaf1", size=(38, 32))
    s.node("LF2", "l3switch", 1020, 800, "Leaf2", size=(38, 32))
    for a in ("SP1", "SP2"):
        for b in ("LF1", "LF2"):
            s.link(a, b, GRY, 1.2)
    s.link("HC2", "SP2", GRY, 1.2, "4 3", mid="border")
    # HAN interior
    s.node("NACC", "l2switch", 245, 580, "Access", ["router-on-a-stick, HSRP"])
    s.link("NACC", "HAN-E1", GRY, 1.3)
    s.link("NACC", "HAN-E2", GRY, 1.3)
    s.node("NENG", "user", 120, 690, "R&D engineers", ["VLAN 20"])
    s.node("NGPU", "server", 245, 690, "AI lab GPU cluster", ["10.20.64.0/18"])
    s.node("NGU", "user", 370, 690, "Guests", ["VLAN 60"])
    for n in ("NENG", "NGPU", "NGU"):
        s.link(n, "NACC", GRY, 1)
    # DAD interior
    s.node("DACC", "l2switch", 1355, 580, "Access", ["router-on-a-stick, HSRP"])
    s.link("DACC", "DAD-E1", GRY, 1.3)
    s.link("DACC", "DAD-E2", GRY, 1.3)
    s.node("DAP", "ap", 1225, 690, "Wi-Fi 6/7 APs", ["low-latency roaming"])
    s.node("DIOT", "iot", 1355, 690, "AGVs, scanners", ["VLAN 50, isolated"])
    s.node("DOP", "user", 1485, 690, "Logistics staff", ["VLAN 30"])
    for n in ("DAP", "DIOT", "DOP"):
        s.link(n, "DACC", GRY, 1)
    # overlay
    s.link("HAN-E1", "HCM-E1", A_COL, 1.6, "7 4", points=[(300, 340), (620, 340)], mid="overlay A", mid_t=0.55)
    s.link("HCM-E2", "DAD-E2", B_COL, 1.6, "7 4", points=[(980, 340), (1300, 340)], mid="overlay B", mid_t=0.45)
    s.text(800, 920, "Dashed blue/orange: GRE-over-IPsec overlay, full mesh on each transport, eBGP between sites. "
           "Each site breaks out to the Internet locally (no backhaul through HQ).", 10.5, "#333", False, "middle")
    return s


# =========================================================================== 2. Lab A physical
def physical():
    s = Scene(1720, 1030)
    s.text(860, 28, "EVE-NG topology (campus + WAN) -- physical layout, interfaces and link subnets", 17, "#1f2d3d", True, "middle")
    s.group(560, 50, 600, 160, "Provider cloud (outside TVI)", "#f4f5f7", "#9aa7b5", sub="ISP-A AS 65100 (203.0.113.0/24) | ISP-B AS 65200 (198.51.100.0/24)")
    s.node("ISP-A", "router", 700, 135, "ISP-A", ["SaaS 192.0.2.10, DNS 192.0.2.53"], label_pos="below")
    s.node("ISP-B", "router", 1020, 135, "ISP-B", ["Cloud-B 198.51.100.200"], label_pos="below")
    a, aif, b, bif, net = sot.ISP_PEERING
    s.link("ISP-A", "ISP-B", GRY, 1.6, la=aif, lb=bif, mid=net)
    s.group(20, 262, 470, 508, "HAN -- Hanoi R&D", "#eef7ea", "#7fb069", sub="OSPF 20 | AS 65020 | router-on-a-stick + HSRP")
    s.group(520, 262, 680, 758, "HCM -- Ho Chi Minh City HQ", "#eef4fb", "#7a9cc6", sub="OSPF 10 | AS 65010 | collapsed core + HSRP + LACP")
    s.group(1230, 262, 470, 508, "DAD -- Da Nang Logistics", "#fdf1e7", "#e0a46c", sub="OSPF 30 | AS 65030 | router-on-a-stick + HSRP")
    pos = {"HAN-EDG1": (120, 330), "HAN-EDG2": (390, 330), "HAN-ACC1": (255, 520),
           "HCM-EDG1": (700, 330), "HCM-EDG2": (1020, 330), "HCM-CORE1": (700, 540), "HCM-CORE2": (1020, 540),
           "HCM-ACC1": (860, 740), "DAD-EDG1": (1330, 330), "DAD-EDG2": (1600, 330), "DAD-ACC1": (1465, 520)}
    kind = {"edge": "router", "core": "l3switch", "access": "l2switch"}
    for n, (x, y) in pos.items():
        d = sot.DEVICES[n]
        sub = [f"Lo0 {d['lo0']}"] if d.get("lo0") else [f"VLAN99 {d['svi99']}"]
        sub.append(f"mgmt {d['mgmt']}")
        lp = "below"
        if n in ("HAN-EDG1", "HCM-EDG1", "DAD-EDG1", "HCM-CORE1"):
            lp = "left"
        if n in ("HAN-EDG2", "HCM-EDG2", "DAD-EDG2", "HCM-CORE2", "HAN-ACC1", "DAD-ACC1", "HCM-ACC1"):
            lp = "right"
        s.node(n, kind[d["role"]], x, y, n, sub, label_pos=lp)
    tpos = {"HAN-EDG1": 0.42, "HCM-EDG1": 0.55, "DAD-EDG1": 0.62, "HAN-EDG2": 0.36, "HCM-EDG2": 0.55, "DAD-EDG2": 0.45}
    for i, iif, ce, cif, net in sot.ISP_LINKS:
        s.link(i, ce, A_COL if i == "ISP-A" else B_COL, 1.8, la=iif, lb=cif,
               mid=net, mid_t=tpos[ce], la_t=0.12, lb_t=0.9)
    for site, a, aif, b, bif, v4, v6 in sot.P2P_LINKS:
        if aif.startswith("Vlan"):
            continue
        cross = (a, b) in (("HCM-EDG1", "HCM-CORE2"), ("HCM-EDG2", "HCM-CORE1"))
        s.link(a, b, "#333", 1.6, la=aif, lb=bif, mid=v4, font=8.5, mid_t=0.3 if cross else 0.5)
    s.link("HCM-CORE1", "HCM-CORE2", "#333", 2, double=True, la="Gi0/1-2", lb="Gi0/1-2",
           mid="Po1 LACP trunk + VLAN900 10.10.254.20/30", la_t=0.13, lb_t=0.87, font=8.5)
    for a, aif, b, bif, po in sot.TRUNKS:
        if po:
            continue
        s.link(a, b, "#2e8b8b", 1.6, la=aif, lb=bif, mid="802.1Q", font=8.5)
    # endpoints
    ep_pos = {"PC-HAN-ENG": (90, 690), "PC-HAN-PHONE": (255, 690), "PC-HAN-GUEST": (420, 690),
              "PC-HCM-EXEC": (590, 930), "PC-HCM-CORP": (730, 930), "PC-HCM-GUEST": (870, 930),
              "PC-HCM-PHONE": (1010, 930), "HCM-SRV1": (1135, 930),
              "PC-DAD-LOG": (1290, 690), "PC-DAD-IOT": (1405, 690), "PC-DAD-PHONE": (1520, 690), "PC-DAD-GUEST": (1640, 690)}
    for sw, pif, ep, epif, data, voice in sot.ACCESS_PORTS:
        x, y = ep_pos[ep]
        site = sot.DEVICES[sw]["site"]
        net = sot.site_subnet(site, data)["v4"]
        if ep == "HCM-SRV1":
            s.node(ep, "server", x, y, ep, [f"VLAN {data}  {sot.DEVICES[ep]['ip']}", "DHCP / DNS / NTP / IP SLA"])
        else:
            s.node(ep, "pc", x, y, ep.replace("PC-", ""), [f"VLAN {data} {sot.VLANS[data]}", net])
        s.link(sw, ep, "#888", 1.2, la=pif, la_t=0.4)
    s.text(1215, 820, "Out-of-band management (not drawn):\nGi0/0 of every node -> EVE-NG Cloud0\n"
           "172.16.99.0/24, automation host .1\n\nOverlay tunnels: see routing diagram.\n"
           "vIOS: set 6 NICs (uses Gi0/0-Gi0/4)\n\nDC fabric: HCM-CORE1/2 Gi1/2 ->\nDC-LEAF1/2 Eth5 (see DC diagram)", 10, "#222", box="#ffffff")
    return s


# =========================================================================== 3. routing / overlay
def routing():
    s = Scene(1600, 960)
    s.text(800, 30, "Routing design -- OSPF underlay per site, eBGP overlay over two IPsec transports", 17, "#1f2d3d", True, "middle")
    s.group(560, 55, 480, 150, "Internet transports", "#f4f5f7", "#9aa7b5")
    s.node("ISP-A", "router", 680, 140, "ISP-A  AS 65100", ["default-originate only"], label_pos="below")
    s.node("ISP-B", "router", 920, 140, "ISP-B  AS 65200", ["default-originate only"], label_pos="below")
    s.link("ISP-A", "ISP-B", GRY, 1.3)
    s.group(30, 300, 430, 330, "AS 65020 -- HAN", "#eef7ea", "#7fb069", sub="announces 10.20.0.0/16 + 2001:db8:a020::/48 only")
    s.group(1140, 300, 430, 330, "AS 65030 -- DAD", "#fdf1e7", "#e0a46c", sub="announces 10.30.0.0/16 + 2001:db8:a030::/48 only")
    s.group(520, 560, 560, 380, "AS 65010 -- HCM", "#eef4fb", "#7a9cc6", sub="announces 10.10.0.0/16 + 2001:db8:a010::/48 only")
    s.group(60, 470, 370, 140, "OSPFv2/v3 process 20, area 0", "#ffffff", "#7fb069", dashed=False, sub="Lo0s, interlink, LAN sub-interfaces (passive)")
    s.group(1170, 470, 370, 140, "OSPFv2/v3 process 30, area 0", "#ffffff", "#e0a46c", dashed=False, sub="Lo0s, interlink, LAN sub-interfaces (passive)")
    s.group(560, 760, 480, 165, "OSPFv2/v3 process 10, area 0", "#ffffff", "#7a9cc6", dashed=False,
            sub="E2 default + remote /16s redistributed from eBGP at the edges")
    s.node("HAN-EDG1", "router", 130, 380, "HAN-EDG1", ["10.20.255.1"], label_pos="below")
    s.node("HAN-EDG2", "router", 360, 380, "HAN-EDG2", ["10.20.255.2"], label_pos="below")
    s.node("DAD-EDG1", "router", 1240, 380, "DAD-EDG1", ["10.30.255.1"], label_pos="below")
    s.node("DAD-EDG2", "router", 1470, 380, "DAD-EDG2", ["10.30.255.2"], label_pos="below")
    s.node("HCM-EDG1", "router", 660, 660, "HCM-EDG1", ["10.10.255.1"], label_pos="left")
    s.node("HCM-EDG2", "router", 940, 660, "HCM-EDG2", ["10.10.255.2"], label_pos="right")
    s.node("HCM-CORE1", "l3switch", 680, 850, "HCM-CORE1", ["10.10.255.3"], label_pos="left")
    s.node("HCM-CORE2", "l3switch", 920, 850, "HCM-CORE2", ["10.10.255.4"], label_pos="right")
    s.node("HAN-LAN", "l2switch", 245, 560, "VLAN 20/40/60/99", label_pos="right")
    s.node("DAD-LAN", "l2switch", 1355, 560, "VLAN 30/40/50/60/99", label_pos="right")
    for a, b in (("HAN-EDG1", "HAN-EDG2"), ("DAD-EDG1", "DAD-EDG2"), ("HCM-EDG1", "HCM-EDG2")):
        s.link(a, b, GRN, 1.8, ":" if False else "2 3", mid="iBGP (Lo0) + OSPF", font=8.5)
    for e in ("HCM-EDG1", "HCM-EDG2"):
        for c in ("HCM-CORE1", "HCM-CORE2"):
            s.link(e, c, "#555", 1.3)
    s.link("HCM-CORE1", "HCM-CORE2", "#555", 1.6, double=True)
    for e in ("HAN-EDG1", "HAN-EDG2"):
        s.link(e, "HAN-LAN", "#555", 1.2)
    for e in ("DAD-EDG1", "DAD-EDG2"):
        s.link(e, "DAD-LAN", "#555", 1.2)
    for e in ("HAN-EDG1", "HCM-EDG1", "DAD-EDG1"):
        s.link(e, "ISP-A", "#9aa7b5", 1.1, mid="eBGP" if e == "HAN-EDG1" else None, mid_t=0.6)
    for e in ("HAN-EDG2", "HCM-EDG2", "DAD-EDG2"):
        s.link(e, "ISP-B", "#9aa7b5", 1.1, mid="eBGP" if e == "DAD-EDG2" else None, mid_t=0.6)
    lab = {11: "Tu11 10.0.0.0/30", 12: "Tu12 10.0.0.4/30", 13: "Tu13 10.0.0.16/30",
           21: "Tu21 10.0.0.8/30", 22: "Tu22 10.0.0.12/30", 23: "Tu23 10.0.0.20/30"}
    pts = {13: [(130, 255), (1240, 255)], 23: [(360, 280), (1470, 280)]}
    for num, a, b, v4, v6, plane in sot.TUNNELS:
        col = A_COL if plane == "A" else B_COL
        s.link(a, b, col, 2.2, "8 4", mid=f"{lab[num]}\neBGP v4+v6", points=pts.get(num), font=8.5,
               mid_t=0.5 if num in (13, 23) else 0.42)
    s.text(245, 770, "Plane A (blue): EDG1s over ISP-A\nPlane B (orange): EDG2s over ISP-B\n"
           "GRE + IPsec (IKEv2, AES-256, SHA-256)\nBGP timers 5/15 s per tunnel\n"
           "Inbound: enterprise /16s only\nOutbound: own site aggregate only\n(no transit, no default via tunnels)",
           10.5, "#222", box="#ffffff")
    s.text(1355, 760, "Failover paths\n1. Tunnel/ISP-A down -> plane B\n2. EDG1 down -> HSRP + iBGP to EDG2\n"
           "3. Core link down -> OSPF ECMP\nInternet: local PAT at every edge\nISP sends default only", 10.5, "#222", box="#ffffff")
    return s


# =========================================================================== 4. HCM L2/L3
def hcm_detail():
    s = Scene(1400, 900)
    s.text(700, 30, "HCM HQ campus -- Layer 3 / Layer 2 boundary, HSRP and STP alignment", 17, "#1f2d3d", True, "middle")
    s.group(40, 55, 1320, 290, "Layer 3 domain -- routed /30 links, OSPF 10 area 0 (point-to-point), ECMP", "#eef4fb", "#7a9cc6")
    s.group(40, 365, 1320, 520, "Layer 2 domain -- 802.1Q trunks, native VLAN 999, Rapid-PVST+, LACP", "#eef7ea", "#7fb069")
    s.node("HCM-EDG1", "router", 420, 125, "HCM-EDG1", ["Lo0 10.10.255.1"], label_pos="left")
    s.node("HCM-EDG2", "router", 980, 125, "HCM-EDG2", ["Lo0 10.10.255.2"], label_pos="right")
    s.node("HCM-CORE1", "l3switch", 420, 330, "HCM-CORE1", ["Lo0 10.10.255.3"], label_pos="left")
    s.node("HCM-CORE2", "l3switch", 980, 330, "HCM-CORE2", ["Lo0 10.10.255.4"], label_pos="right")
    s.node("HCM-ACC1", "l2switch", 700, 600, "HCM-ACC1", ["VLAN99 10.10.44.15, no ip routing"], label_pos="below")
    for a, b in (("HCM-EDG1", "HCM-CORE1"), ("HCM-EDG1", "HCM-CORE2"), ("HCM-EDG2", "HCM-CORE1"), ("HCM-EDG2", "HCM-CORE2"), ("HCM-EDG1", "HCM-EDG2")):
        aif, bif, v4 = p2p(a, b)
        cross = (a, b) in (("HCM-EDG1", "HCM-CORE2"), ("HCM-EDG2", "HCM-CORE1"))
        s.link(a, b, "#333", 1.6, la=aif, lb=bif, mid=v4, font=9, mid_t=0.3 if cross else 0.5)
    s.link("HCM-CORE1", "HCM-CORE2", "#333", 2.2, double=True, la="Gi0/1-2", lb="Gi0/1-2",
           mid="Po1 (LACP active)\ntrunk 10,12,40,60,70,80,99,900", font=9)
    s.link("HCM-CORE1", "HCM-ACC1", A_COL, 2.0, la="Gi0/3\nroot guard", lb="Gi0/1",
           mid="FWD: 10,12,40,80\nALT/BLK: 60,70,99", font=9)
    s.link("HCM-CORE2", "HCM-ACC1", B_COL, 2.0, la="Gi0/3\nroot guard", lb="Gi0/2",
           mid="FWD: 60,70,99\nALT/BLK: 10,12,40,80", font=9)
    s.text(215, 520, "HCM-CORE1\nSTP root (24576): 10,12,40,80,900\nSTP backup (28672): 60,70,99\n"
           "HSRP active (prio 110): 10,12,40,80\nSVIs .2 / ::2, VIP .1 / FE80::1", 10.5, "#1f2d3d", box="#ffffff")
    s.text(1190, 520, "HCM-CORE2\nSTP root (24576): 60,70,99\nSTP backup (28672): 10,12,40,80,900\n"
           "HSRP active (prio 110): 60,70,99\nSVIs .3 / ::3, VIP .1 / FE80::1", 10.5, "#1f2d3d", box="#ffffff")
    ep = [("PC-HCM-EXEC", 300, "Gi1/0", "V10 EXEC 10.10.32.0/24\n+ voice V40"), ("PC-HCM-CORP", 500, "Gi1/1", "V12 CORP 10.10.0.0/24\n+ voice V40"),
          ("PC-HCM-GUEST", 700, "Gi1/2", "V60 GUEST 10.10.36.0/24\nACL-GUEST-IN"), ("PC-HCM-PHONE", 900, "Gi1/3", "V40 VOICE 10.10.16.0/24"),
          ("HCM-SRV1", 1100, "Gi2/0", "V80 SERVERS 10.10.43.0/24\nDHCP/DNS/NTP .10")]
    for n, x, pif, lab in ep:
        s.node(n, "server" if n == "HCM-SRV1" else "pc", x, 790, n.replace("PC-", ""), lab.split("\n"))
        s.link("HCM-ACC1", n, "#888", 1.2, la=pif, la_t=0.3)
    s.text(190, 700, "Access-port protection\nportfast + BPDU guard\nport-security (sticky, max 2-3)\n"
           "DHCP snooping (uplinks trusted)\nDynamic ARP Inspection\nerrdisable auto-recovery 120 s", 10, "#222", box="#ffffff")
    return s


# =========================================================================== 5. DC fabric
def dc():
    s = Scene(1400, 800)
    s.text(700, 30, "HQ data-centre fabric (lab): OSPF + LDP underlay, MP-BGP VPNv4 overlay, tenant VRFs, border to the campus core",
           15.5, "#1f2d3d", True, "middle")
    s.group(240, 55, 920, 200, "Spine layer -- P routers + VPNv4 route reflectors (AS 65011)", "#eef4fb", "#7a9cc6")
    s.group(240, 290, 920, 480, "Leaf layer -- PE routers: VRF TENANT-PROD (RT 65011:100), VRF TENANT-DEV (RT 65011:200)",
            "#eef7ea", "#7fb069")
    s.group(15, 290, 205, 300, "HQ campus", "#f4f5f7", "#9aa7b5", sub="OSPF 10 area 0")
    s.group(1180, 290, 205, 300, "HQ campus", "#f4f5f7", "#9aa7b5", sub="OSPF 10 area 0")
    s.node("DC-SPINE1", "router", 450, 150, "DC-SPINE1", ["Lo0 10.10.191.1"], label_pos="left")
    s.node("DC-SPINE2", "router", 950, 150, "DC-SPINE2", ["Lo0 10.10.191.2"], label_pos="right")
    s.node("DC-LEAF1", "router", 450, 420, "DC-LEAF1", ["Lo0 10.10.191.11"])
    s.node("DC-LEAF2", "router", 950, 420, "DC-LEAF2", ["Lo0 10.10.191.12"])
    s.node("HCM-CORE1", "l3switch", 117, 420, "HCM-CORE1")
    s.node("HCM-CORE2", "l3switch", 1283, 420, "HCM-CORE2")
    for sp, sif, lf, lif, net in sot.DC["fabric_links"]:
        cross = (sp, lf) in (("DC-SPINE1", "DC-LEAF2"), ("DC-SPINE2", "DC-LEAF1"))
        s.link(sp, lf, "#333", 1.8, la=sif, lb=lif, mid=net, font=9, mid_t=0.3 if cross else 0.5)
    for core, cif, lf, lif, net in sot.BORDER_LINKS:
        s.link(core, lf, "#2e8540", 2.0, la=cif, lb=lif, mid=f"{net}\nOSPF 11 in VRF PROD", font=8.5, la_t=0.18, lb_t=0.8)
    s.link("DC-LEAF1", "DC-LEAF2", "#7b3fa0", 2.2, "8 4", mid="MPLS LSP via either spine\nVPN label per tenant", font=9.5)
    pos = {"DC-H1": 300, "DC-H3": 560, "DC-H2": 840, "DC-H4": 1100}
    for lf, lif, h, vrf, net, hip in sot.DC["hosts"]:
        s.node(h, "server", pos[h], 670, h, [f"{vrf}", f"{hip} (GW .1)"])
        s.link(lf, h, "#1f77b4" if vrf.endswith("PROD") else "#d9711c", 1.4, la=lif, la_t=0.4)
    s.text(700, 565, "H1 <-> H2 (PROD) and H3 <-> H4 (DEV): routed across the fabric by MP-BGP VPNv4\n"
           "H1 <-> H3: blocked -- different VRFs, no shared route-target\n"
           "PROD <-> campus/branches: leaf -> HCM core via OSPF in VRF PROD; DEV has no border", 10.5, "#222", box="#ffffff")
    return s


SCENES = {"01-logical-architecture": logical, "02-labA-physical": physical, "03-routing-overlay": routing,
          "04-hcm-l2-l3": hcm_detail, "05-dc-fabric": dc}

if __name__ == "__main__":
    for name, fn in SCENES.items():
        sc = fn()
        svg = os.path.join(OUT, f"{name}.svg")
        open(svg, "w").write(sc.svg())
        open(os.path.join(OUT, f"{name}.drawio"), "w").write(sc.drawio(name))
        subprocess.run(["rsvg-convert", "-f", "pdf", "-o", os.path.join(OUT, f"{name}.pdf"), svg], check=True)
        subprocess.run(["rsvg-convert", "-z", "1.5", "-o", os.path.join(OUT, f"{name}.png"), svg], check=True)
        print("wrote", name)
