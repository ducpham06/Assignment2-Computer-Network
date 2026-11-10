#!/usr/bin/env python3
"""
Offline consistency checks on the RENDERED configurations (not on the SoT),
so template bugs are caught before anything is pasted into EVE-NG.

    python3 tools/validate.py          -> prints PASS/FAIL per check, exit 1 on failure

What it cannot do: prove that IOS accepts every command or that protocols
converge. That is what the lab verification plan (docs/test-plan.md) is for.
"""
import glob
import ipaddress as ip
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sot  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAIL = []
CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, ok, detail))
    if not ok:
        FAIL.append(name)


# ---------------------------------------------------------------- parsing
def parse_ios(path):
    dev = os.path.basename(path)[:-4]
    txt = open(path).read()
    lines = txt.splitlines()
    cfg = dict(dev=dev, text=txt, ifs={}, bgp_as=None, nbrs={}, hsrp={}, stp={}, vlans=set(),
               acl_defs=set(), acl_refs=set(), pm_defs=set(), pm_refs=set(), cm_defs=set(), cm_refs=set(),
               helpers=set(), pools={}, ospf_pid={}, passive_default={}, no_passive={}, tunnels={},
               isakmp=False)
    cur, section = None, None
    for raw in lines:
        if raw.startswith("!") or not raw.strip():
            continue
        if not raw.startswith(" "):
            section, cur = raw, None
            m = re.match(r"interface (\S+)", raw)
            if m:
                cur = m.group(1)
                cfg["ifs"][cur] = dict(lines=[], v4=None, v6=[], ospf=None, mode=None, allowed=None,
                                       access=None, shutdown=False, channel=None)
            m = re.match(r"router bgp (\d+)", raw)
            if m:
                cfg["bgp_as"] = int(m.group(1))
            m = re.match(r"(ipv6 )?router ospf (\d+)", raw)
            if m:
                key = "v6" if m.group(1) else "v4"
                cfg["ospf_pid"][key] = int(m.group(2))
                cfg["no_passive"][key] = set()
            m = re.match(r"spanning-tree vlan (\S+) priority (\d+)", raw)
            if m:
                for v in m.group(1).split(","):
                    cfg["stp"][int(v)] = int(m.group(2))
            m = re.match(r"vlan (\d+)$", raw)
            if m:
                cfg["vlans"].add(int(m.group(1)))
            m = re.match(r"ip(v6)? access-list (?:extended |standard )?(\S+)", raw)
            if m:
                cfg["acl_defs"].add(m.group(2))
            m = re.match(r"policy-map (?:type inspect )?(\S+)", raw)
            if m:
                cfg["pm_defs"].add(m.group(1))
            m = re.match(r"class-map (?:type inspect )?(?:match-any |match-all )?(\S+)", raw)
            if m:
                cfg["cm_defs"].add(m.group(1))
            m = re.match(r"ip dhcp pool (\S+)", raw)
            if m:
                cfg["pools"][m.group(1)] = {}
            m = re.match(r"zone-pair .*", raw)
            continue
        s = raw.strip()
        if section and section.startswith("interface") and cur:
            I = cfg["ifs"][cur]
            I["lines"].append(s)
            m = re.match(r"ip address (\S+) (\S+)$", s)
            if m:
                I["v4"] = ip.ip_interface(f"{m.group(1)}/{m.group(2)}")
            m = re.match(r"ipv6 address (\S+/\d+)$", s)
            if m:
                I["v6"].append(ip.ip_interface(m.group(1)))
            m = re.match(r"ip ospf (\d+) area", s)
            if m:
                I["ospf"] = int(m.group(1))
            m = re.match(r"standby (\d+) (ip|priority|ipv6) (\S+)", s)
            if m:
                g = int(m.group(1))
                cfg["hsrp"].setdefault(g, {})[m.group(2)] = m.group(3)
                cfg["hsrp"][g]["if"] = cur
            m = re.match(r"switchport mode (\S+)", s)
            if m:
                I["mode"] = m.group(1)
            m = re.match(r"switchport trunk allowed vlan (\S+)", s)
            if m:
                I["allowed"] = set(int(x) for x in m.group(1).split(","))
            m = re.match(r"switchport (?:access|voice) vlan (\d+)", s)
            if m:
                I.setdefault("vl", set()).add(int(m.group(1)))
            m = re.match(r"channel-group (\d+)", s)
            if m:
                I["channel"] = int(m.group(1))
            if s == "shutdown":
                I["shutdown"] = True
            m = re.match(r"ip(?:v6)? (?:access-group|traffic-filter) (\S+)", s)
            if m:
                cfg["acl_refs"].add(m.group(1))
            m = re.match(r"service-policy (?:input|output) (\S+)", s)
            if m:
                cfg["pm_refs"].add(m.group(1))
            m = re.match(r"ip helper-address (\S+)", s)
            if m:
                cfg["helpers"].add(m.group(1))
            m = re.match(r"tunnel (source|destination) (\S+)", s)
            if m:
                cfg["tunnels"].setdefault(cur, {})[m.group(1)] = m.group(2)
        elif section and section.startswith("router bgp"):
            m = re.match(r"neighbor (\S+) remote-as (\d+)", s)
            if m:
                cfg["nbrs"][m.group(1)] = int(m.group(2))
            m = re.match(r"neighbor \S+ prefix-list (\S+)", s)
        elif section and re.match(r"(ipv6 )?router ospf", section):
            key = "v6" if section.startswith("ipv6") else "v4"
            if s == "passive-interface default":
                cfg["passive_default"][key] = True
            m = re.match(r"no passive-interface (\S+)", s)
            if m:
                cfg["no_passive"][key].add(m.group(1))
        elif section and section.startswith("ip dhcp pool"):
            pool = section.split()[-1]
            m = re.match(r"network (\S+) (\S+)", s)
            if m:
                cfg["pools"][pool]["net"] = ip.ip_network(f"{m.group(1)}/{m.group(2)}")
            m = re.match(r"default-router (\S+)", s)
            if m:
                cfg["pools"][pool]["gw"] = m.group(1)
        elif section and (section.startswith("policy-map") or section.startswith("zone-pair")):
            m = re.match(r"class (?:type inspect )?(\S+)", s)
            if m and m.group(1) != "class-default":
                cfg["cm_refs"].add(m.group(1))
            m = re.match(r"service-policy (?:type inspect )?(\S+)", s)
            if m:
                cfg["pm_refs"].add(m.group(1))
        elif section and section.startswith("class-map"):
            m = re.match(r"match access-group name (\S+)", s)
            if m:
                cfg["acl_refs"].add(m.group(1))
        elif section and section.startswith("line vty"):
            m = re.match(r"access-class (\S+)", s)
            if m:
                cfg["acl_refs"].add(m.group(1))
    m = re.search(r"ip nat inside source list (\S+)", txt)
    if m:
        cfg["acl_refs"].add(m.group(1))
    return cfg


C = {}
for p in sorted(glob.glob(os.path.join(ROOT, "configs", "labA", "*.cfg"))):
    c = parse_ios(p)
    C[c["dev"]] = c

# ---------------------------------------------------------------- 1. address plan
pools = [(s, v, ip.ip_network(p)) for s, v, p, *_ in sot.POOLS]
ov = []
for i in range(len(pools)):
    for j in range(i + 1, len(pools)):
        if pools[i][2].overlaps(pools[j][2]):
            ov.append((pools[i], pools[j]))
check("IPv4 design pools do not overlap", not ov, str(ov))
outside = [p for p in pools if p[0] in sot.SITES and not p[2].subnet_of(ip.ip_network(sot.SITES[p[0]]["v4"]))]
check("Every pool sits inside its site summary (/16)", not outside, str(outside))
bad = []
for site, subs in sot.SUBNETS.items():
    for s in subs:
        n = ip.ip_network(s["v4"])
        if not any(p[0] == site and p[1] == s["vlan"] and n.subnet_of(p[2]) for p in pools):
            bad.append((site, s["vlan"]))
        if s.get("v6"):
            n6 = ip.ip_network(s["v6"])
            if not n6.subnet_of(ip.ip_network(sot.SITES[site]["v6"])) or n6.prefixlen != 64:
                bad.append((site, s["vlan"], "v6"))
check("Every deployed subnet is carved from its VLAN pool; v6 /64 inside site /48", not bad, str(bad))
small = [p for p in sot.POOLS if p[3] and ip.ip_network(p[2]).num_addresses - 2 < p[3]]
check("Every pool is large enough for its 2030 demand", not small, str(small))

# ---------------------------------------------------------------- 2. unique addresses
seen, dup = {}, []
for d, c in C.items():
    for ifn, I in c["ifs"].items():
        for a in ([I["v4"]] if I["v4"] else []) + I["v6"]:
            k = str(a.ip)
            if k in seen:
                dup.append((k, seen[k], f"{d} {ifn}"))
            seen[k] = f"{d} {ifn}"
check("No duplicate interface IP addresses (v4+v6) across Lab A", not dup, str(dup))
owner = {}
for d, c in C.items():
    for ifn, I in c["ifs"].items():
        if I["v4"]:
            owner[str(I["v4"].ip)] = (d, ifn)
        for a in I["v6"]:
            owner[str(a.ip)] = (d, ifn)

# ---------------------------------------------------------------- 3. links
def if_addr(dev, ifs):
    I = C[dev]["ifs"].get(sot.full_if(ifs))
    return I


bad = []
for site, a, aif, b, bif, v4, v6 in sot.P2P_LINKS:
    A, B = if_addr(a, aif), if_addr(b, bif)
    if not A or not B or A["v4"].network != B["v4"].network or A["v4"].ip == B["v4"].ip:
        bad.append((a, aif, b, bif))
    elif A["ospf"] != B["ospf"] or A["ospf"] is None:
        bad.append((a, aif, b, bif, "ospf pid"))
    for dev, ifn in ((a, aif), (b, bif)):
        if sot.full_if(ifn) not in C[dev]["no_passive"]["v4"]:
            bad.append((dev, ifn, "passive"))
for isp, iif, ce, cif, net in sot.ISP_LINKS:
    A, B = if_addr(isp, iif), if_addr(ce, cif)
    if not A or not B or A["v4"].network != B["v4"].network:
        bad.append((isp, ce))
check("Both ends of every routed / ISP link share one subnet; OSPF links non-passive & same process", not bad, str(bad))

bad = []
for d, c in C.items():
    for tif, t in c["tunnels"].items():
        num = tif.replace("Tunnel", "")
        src_ip = str(c["ifs"][t["source"]]["v4"].ip)
        peer = owner.get(t["destination"])
        if not peer:
            bad.append((d, tif, "dest unknown"))
            continue
        pt = C[peer[0]]["tunnels"].get(tif)
        if not pt or pt["destination"] != src_ip:
            bad.append((d, tif, "asymmetric"))
            continue
        if C[peer[0]]["ifs"][tif]["v4"].network != c["ifs"][tif]["v4"].network:
            bad.append((d, tif, "inner subnet"))
check("Tunnel source/destination symmetric and inner subnets match (6 tunnels x 2 ends)",
      not bad and sum(len(c["tunnels"]) for c in C.values()) == 12, str(bad))

# ---------------------------------------------------------------- 4. BGP
bad, sessions = [], 0
for d, c in C.items():
    for nip, ras in c["nbrs"].items():
        o = owner.get(nip)
        if not o:
            bad.append((d, nip, "neighbor IP not owned by any device"))
            continue
        pd = C[o[0]]
        if pd["bgp_as"] != ras:
            bad.append((d, nip, f"remote-as {ras} but {o[0]} is AS {pd['bgp_as']}"))
        my_ips = {str(I["v4"].ip) for I in c["ifs"].values() if I["v4"]} | \
                 {str(a.ip) for I in c["ifs"].values() for a in I["v6"]}
        back = [x for x, a in pd["nbrs"].items() if x in my_ips and a == c["bgp_as"]]
        if not back:
            bad.append((d, nip, "no reverse neighbor statement"))
        sessions += 1
check(f"BGP: every neighbor exists, AS numbers match, sessions are bidirectional ({sessions // 2} sessions)",
      not bad, str(bad))
bad = []
for d, c in C.items():
    for nip in c["nbrs"]:
        if not re.search(rf"neighbor {re.escape(nip)} activate", c["text"]):
            bad.append((d, nip))
check("BGP: every neighbor is activated in an address-family", not bad, str(bad))

# ---------------------------------------------------------------- 5. HSRP / STP
bad = []
for site, (ga, gb) in sot.GATEWAYS.items():
    A, B = C[ga]["hsrp"], C[gb]["hsrp"]
    if set(A) != set(B):
        bad.append((site, "group mismatch"))
    for g in A:
        if A[g].get("ip") != B[g].get("ip") or A[g].get("ipv6") != B[g].get("ipv6"):
            bad.append((site, g, "VIP"))
        if sorted([A[g]["priority"], B[g]["priority"]]) != ["100", "110"]:
            bad.append((site, g, "priority"))
        if g < 1000:
            vip = ip.ip_address(A[g]["ip"])
            if vip not in C[ga]["ifs"][A[g]["if"]]["v4"].network:
                bad.append((site, g, "VIP outside subnet"))
check("HSRP: same VIP on both gateways, one active (110) and one standby (100), VIP in subnet", not bad, str(bad))
bad = []
for core in sot.GATEWAYS["HCM"]:
    c = C[core]
    for g, h in c["hsrp"].items():
        if g >= 1000:
            continue
        active = h["priority"] == "110"
        root = c["stp"].get(g) == 24576
        if active != root:
            bad.append((core, g))
check("STP root bridge aligned with HSRP active gateway per VLAN (HQ cores)", not bad, str(bad))

# ---------------------------------------------------------------- 6. L2 consistency
bad = []
for d, c in C.items():
    for ifn, I in c["ifs"].items():
        for v in I.get("vl", set()):
            if v not in c["vlans"]:
                bad.append((d, ifn, v, "access VLAN not defined"))
        if I["allowed"]:
            for v in I["allowed"]:
                if v not in c["vlans"]:
                    bad.append((d, ifn, v, "trunk VLAN not defined"))
for a, aif, b, bif, po in sot.TRUNKS:
    A, B = if_addr(a, aif), if_addr(b, bif)
    if A["mode"] == "trunk" and B["mode"] == "trunk" and A["allowed"] != B["allowed"]:
        bad.append((a, aif, b, bif, "allowed list differs"))
    if (A["channel"] or None) != (B["channel"] or None):
        bad.append((a, aif, b, bif, "channel-group"))
for sw, pif, ep, epif, data, voice in sot.ACCESS_PORTS:
    site = sot.DEVICES[sw]["site"]
    gw_vlans = {s["vlan"] for s in sot.SUBNETS[site]}
    if data not in gw_vlans:
        bad.append((sw, pif, data, "no gateway for VLAN"))
    up = [t for t in sot.TRUNKS if sw in (t[0], t[2])]
    for t in up:
        I = if_addr(sw, t[1] if t[0] == sw else t[3])
        if data not in I["allowed"]:
            bad.append((sw, data, "not allowed on uplink"))
check("VLANs defined before use; trunk allowed-lists and LACP membership match on both ends", not bad, str(bad))

# ---------------------------------------------------------------- 7. DHCP / relay
srv = C["HCM-SRV1"]
bad = []
for site, subs in sot.SUBNETS.items():
    for s in subs:
        n = ip.ip_network(s["v4"])
        pool = [p for p in srv["pools"].values() if p.get("net") == n]
        if s.get("dhcp"):
            if not pool or pool[0]["gw"] != sot.nth(s["v4"], 1):
                bad.append((site, s["vlan"], "pool/gateway"))
            for g in sot.GATEWAYS[site]:
                I = [I for I in C[g]["ifs"].values() if I["v4"] and I["v4"].network == n][0]
                if f"ip helper-address {sot.DHCP_DNS_SERVER}" not in I["lines"]:
                    bad.append((g, s["vlan"], "no relay"))
check("Every DHCP-enabled VLAN has a pool on HCM-SRV1 (gateway = HSRP VIP) and a relay on both gateways",
      not bad, str(bad))

# ---------------------------------------------------------------- 8. references
bad = []
for d, c in C.items():
    for r in c["acl_refs"] - c["acl_defs"]:
        bad.append((d, "ACL", r))
    for r in c["pm_refs"] - c["pm_defs"]:
        bad.append((d, "policy-map", r))
    for r in c["cm_refs"] - c["cm_defs"]:
        bad.append((d, "class-map", r))
check("Every referenced ACL / class-map / policy-map is defined on the same device", not bad, str(bad))

bad = []
for d, c in C.items():
    if sot.DEVICES[d]["role"] != "edge":
        continue
    for ifn, I in c["ifs"].items():
        if ifn.startswith(("Loopback", "GigabitEthernet0/0")) or ifn == "GigabitEthernet0/2" and not I["v4"]:
            continue
        if not any(l.startswith("zone-member security") for l in I["lines"]):
            bad.append((d, ifn))
check("ZBF: every data-plane interface of every WAN edge is in a security zone", not bad, str(bad))

# ---------------------------------------------------------------- 9. Lab B (EOS)
eos = {os.path.basename(p)[:-4]: open(p).read() for p in glob.glob(os.path.join(ROOT, "configs", "labB", "*.cfg"))}
bad = []
for s, sif, lf, lif, net in sot.DC["fabric_links"]:
    a = re.search(rf"interface {sif}\n(?:   .*\n)*?   ip address (\S+)", eos[s]).group(1)
    b = re.search(rf"interface {lif}\n(?:   .*\n)*?   ip address (\S+)", eos[lf]).group(1)
    if ip.ip_interface(a).network != ip.ip_interface(b).network or a == b:
        bad.append((s, lf))
lo = {d: re.search(r"interface Loopback0\n(?:   .*\n)*?   ip address (\S+)/32", t).group(1) for d, t in eos.items()}
for d, t in eos.items():
    for n in re.findall(r"neighbor (\d+\.\d+\.\d+\.\d+) peer group", t):
        if n not in lo.values():
            bad.append((d, n, "EVPN peer loopback unknown"))
vnis = {d: sorted(re.findall(r"vxlan vlan (\d+) vni (\d+)", t)) for d, t in eos.items() if "Vxlan1" in t}
if len({str(v) for v in vnis.values()}) != 1:
    bad.append(("VNI map differs", vnis))
check("Lab B: fabric /31s match, EVPN peers are real loopbacks, VLAN-VNI map identical on all leaves",
      not bad, str(bad))

# ---------------------------------------------------------------- 10. RAM budget
ramA = sum(sot.RAM_MB[d["platform"]] for d in sot.DEVICES.values() if d["lab"] == "A")
ramB = sum(sot.RAM_MB[d["platform"]] for d in sot.DEVICES.values() if d["lab"] == "B" and not d.get("optional"))
check(f"RAM budget: Lab A = {ramA / 1024:.1f} GB, Lab B (1 spine) = {ramB / 1024:.1f} GB -- each fits a 12 GB host",
      ramA <= 9 * 1024 and ramB <= 7 * 1024)

# ---------------------------------------------------------------- report
w = max(len(n) for n, _, _ in CHECKS)
for n, ok, det in CHECKS:
    print(f"[{'PASS' if ok else 'FAIL'}] {n}")
    if not ok:
        print("       ", det[:600])
print(f"\n{len(CHECKS) - len(FAIL)}/{len(CHECKS)} checks passed")
sys.exit(1 if FAIL else 0)
