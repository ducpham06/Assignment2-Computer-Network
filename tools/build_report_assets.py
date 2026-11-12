#!/usr/bin/env python3
"""Generate LaTeX tables and config excerpts for the report from the SoT and rendered configs."""
import ipaddress as ip
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sot  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "report", "generated")
os.makedirs(GEN, exist_ok=True)


def tex(s):
    return (str(s).replace("\\", r"\textbackslash{}").replace("_", r"\_").replace("&", r"\&")
            .replace("%", r"\%").replace("#", r"\#"))


def w(name, text):
    open(os.path.join(GEN, name), "w").write(text)


def fmt(n):
    return f"{n:,}".replace(",", "{,}")


# ---------------------------------------------------------------- site summary
rows = []
for k, s in sot.SITES.items():
    rows.append(f"{k} & {tex(s['name'])} & \\texttt{{{s['v4']}}} & \\texttt{{{s['v6']}}} & {s['asn']} & {s['ospf']} & "
                f"{fmt(s['users_now'])} & {fmt(s['users_2030'])} \\\\")
w("tab_sites.tex", "\n".join(rows))

# ---------------------------------------------------------------- pools
rows = []
for site, v, p, need, note in sot.POOLS:
    n = ip.ip_network(p)
    usable = n.num_addresses - 2
    util = f"{need / usable * 100:.0f}\\%" if need else "--"
    vname = f"{v} {tex(sot.VLANS[v])}" if isinstance(v, int) else tex(v)
    rows.append(f"{site} & {vname} & \\texttt{{{p}}} & {fmt(usable)} & {fmt(need) if need else '--'} & {util} & {tex(note)} \\\\")
w("tab_pools.tex", "\n".join(rows))

# ---------------------------------------------------------------- deployed
rows = []
for site, subs in sot.SUBNETS.items():
    ga, gb = sot.GATEWAYS[site]
    for s in subs:
        act = ga if s["active"] == "A" else gb
        acl = r" \newline ".join(tex(x) for x in (s.get("acl_in"), s.get("acl_out")) if x) or "--"
        rows.append(f"{site} & {s['vlan']} & {tex(sot.VLANS[s['vlan']])} & \\texttt{{{s['v4']}}} & "
                    f"\\texttt{{{s['v6'] or 'IPv4 only'}}} & {tex(act)} & {'relay' if s.get('dhcp') else 'static'} & {acl} \\\\")
w("tab_deployed.tex", "\n".join(rows))

# ---------------------------------------------------------------- links
rows = []
for site, a, aif, b, bif, v4, v6 in sot.P2P_LINKS:
    rows.append(f"{tex(a)} {aif} & {tex(b)} {bif} & \\texttt{{{v4}}} & \\texttt{{{v6}}} \\\\")
for i, iif, ce, cif, net in sot.ISP_LINKS:
    rows.append(f"{tex(i)} {iif} & {tex(ce)} {cif} & \\texttt{{{net}}} & -- \\\\")
for num, a, b, v4, v6, plane in sot.TUNNELS:
    rows.append(f"{tex(a)} Tu{num} & {tex(b)} Tu{num} (plane {plane}) & \\texttt{{{v4}}} & \\texttt{{{v6}}} \\\\")
w("tab_links.tex", "\n".join(rows))

# ---------------------------------------------------------------- devices / RAM
rows, ram = [], {"A": 0, "B": 0}
img = {"vios": "vIOS", "viosl2": "IOSvL2"}
for n, d in sot.DEVICES.items():
    lo6 = sot.lo0_v6(n) if d["lab"] == "A" and d.get("lo0") and d["role"] != "isp" else "--"
    rows.append(f"{tex(n)} & {'DC' if d['lab'] == 'B' else 'C/W'} & {img[d['platform']]} & {d['role']} & \\texttt{{{d.get('lo0', d.get('svi99', d.get('ip', '--')))}}} & "
                f"\\texttt{{{lo6}}} & \\texttt{{{d['mgmt']}}} & {sot.RAM_MB[d['platform']]} \\\\")
    if not d.get("optional"):
        ram[d["lab"]] += sot.RAM_MB[d["platform"]]
w("tab_devices.tex", "\n".join(rows))
w("ram.tex", f"\\newcommand{{\\ramA}}{{{ram['A'] / 1024:.1f}}}\n\\newcommand{{\\ramB}}{{{ram['B'] / 1024:.1f}}}\n"
           f"\\newcommand{{\\ramT}}{{{(ram['A'] + ram['B']) / 1024:.1f}}}\n")

# ---------------------------------------------------------------- config excerpts
CFG = os.path.join(ROOT, "configs")


def block(dev, start, lab="labA", stop_blank=True, max_lines=60):
    txt = open(os.path.join(CFG, lab, f"{dev}.cfg")).read().splitlines()
    out, on = [], False
    for line in txt:
        if not on and re.match(start, line):
            on = True
        elif on and stop_blank and (line == "!" or (line and not line.startswith(" ") and not re.match(start, line))):
            break
        if on:
            out.append(line)
    return out[:max_lines]


def excerpt(name, parts):
    lines = []
    for p in parts:
        lines += p + ["!"]
    w(name, "\n".join(lines[:-1]) + "\n")


excerpt("cfg_hsrp.txt", [block("HCM-CORE1", r"interface Vlan10$")])
excerpt("cfg_lacp.txt", [block("HCM-CORE1", r"interface Port-channel1"), block("HCM-CORE1", r"interface GigabitEthernet0/1$")])
excerpt("cfg_stp.txt", [block("HCM-CORE1", r"spanning-tree mode", stop_blank=False, max_lines=5)])
excerpt("cfg_ospf.txt", [block("HCM-EDG1", r"router ospf 10"), block("HCM-EDG1", r"ipv6 router ospf 10")])
excerpt("cfg_tunnel.txt", [block("HCM-EDG1", r"interface Tunnel11")])
excerpt("cfg_bgp.txt", [block("HCM-EDG1", r"router bgp", max_lines=41)])
excerpt("cfg_prefix.txt", [block("HCM-EDG1", r"ip prefix-list PL-DEFAULT-ONLY", max_lines=20)])
excerpt("cfg_acl_guest.txt", [block("HAN-EDG1", r"ip access-list extended ACL-GUEST-IN")])
excerpt("cfg_acl_iot.txt", [block("DAD-EDG2", r"ip access-list extended ACL-IOT-IN")])
excerpt("cfg_acl_exec.txt", [block("HCM-CORE1", r"ip access-list extended ACL-EXEC-PROTECT")])
excerpt("cfg_zbf.txt", [block("HCM-EDG1", r"zone security INSIDE", max_lines=36, stop_blank=False)[:36]])
excerpt("cfg_nat.txt", [block("HCM-EDG1", r"ip access-list extended ACL-NAT", stop_blank=False, max_lines=5)])
excerpt("cfg_qos.txt", [block("HCM-EDG1", r"policy-map PM-LAN-MARK-IN"), block("HCM-EDG1", r"policy-map PM-WAN-QUEUING"),
                        block("HCM-EDG1", r"policy-map PM-WAN-SHAPE")])
excerpt("cfg_l2sec.txt", [block("DAD-ACC1", r"ip dhcp snooping vlan", stop_blank=False, max_lines=4),
                          block("DAD-ACC1", r"interface GigabitEthernet1/1$")])
excerpt("cfg_dhcp.txt", [block("HCM-SRV1", r"ip dhcp pool HAN-V20"), block("HCM-SRV1", r"ip dhcp pool HCM-V70")])
excerpt("cfg_ipsla.txt", [block("HCM-SRV1", r"ip sla 10$", stop_blank=False, max_lines=6)])
excerpt("cfg_ipsec.txt", [block("HCM-EDG1", r"crypto ikev2 proposal", stop_blank=False, max_lines=22)])
excerpt("cfg_dc_leaf.txt", [block("DC-LEAF1", r"vrf definition TENANT-PROD", lab="labB"),
                            block("DC-LEAF1", r"interface GigabitEthernet0/3$", lab="labB"),
                            block("DC-LEAF1", r"router bgp", lab="labB", stop_blank=False, max_lines=27)])
print("report assets written to report/generated/")

# figures
fig = os.path.join(ROOT, "report", "figures")
os.makedirs(fig, exist_ok=True)
for f in os.listdir(os.path.join(ROOT, "diagrams")):
    if f.endswith(".pdf"):
        shutil.copy(os.path.join(ROOT, "diagrams", f), fig)
