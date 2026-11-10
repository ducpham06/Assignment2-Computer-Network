#!/usr/bin/env python3
"""Render the IP addressing plan (Excel + Markdown) from the SoT."""
import ipaddress as ip
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sot  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "ip-plan")
os.makedirs(OUT, exist_ok=True)

FONT = "Arial"
HDR_FILL = PatternFill("solid", fgColor="1F3864")
SITE_FILL = {"HCM": "DDEBF7", "HAN": "E2EFDA", "DAD": "FCE4D6", "WAN": "EDEDED"}
thin = Side(style="thin", color="BFBFBF")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)


def vname(v):
    return sot.VLANS.get(v, v) if isinstance(v, int) else v


def sheet(wb, title, headers, rows, widths, note=None, site_col=0):
    ws = wb.create_sheet(title)
    r0 = 1
    if note:
        ws.cell(1, 1, note).font = Font(name=FONT, italic=True, size=9, color="595959")
        r0 = 3
    for j, h in enumerate(headers, 1):
        c = ws.cell(r0, j, h)
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = HDR_FILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
    for i, row in enumerate(rows, r0 + 1):
        fill = PatternFill("solid", fgColor=SITE_FILL.get(str(row[site_col]), "FFFFFF")) if site_col is not None else None
        for j, v in enumerate(row, 1):
            if isinstance(v, str) and "{r}" in v:
                v = v.replace("{r}", str(i))
            c = ws.cell(i, j, v)
            c.font = Font(name=FONT, size=10)
            c.border = BORDER
            if fill:
                c.fill = fill
    for j, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws.cell(r0 + 1, 1)
    ws.auto_filter.ref = f"A{r0}:{get_column_letter(len(headers))}{r0 + len(rows)}"
    return ws, r0


wb = Workbook()
wb.remove(wb.active)

# ---- 1. Site summary
rows = []
for k, s in sot.SITES.items():
    n = ip.ip_network(s["v4"])
    rows.append([k, s["name"], s["v4"], n.prefixlen, "=2^(32-D{r})", s["v6"], s["asn"], s["ospf"],
                 s["users_now"], s["users_2030"]])
ws, r0 = sheet(wb, "Site Summary",
               ["Site", "Name", "IPv4 summary", "Prefix len", "IPv4 addresses", "IPv6 /48",
                "BGP AS", "OSPF process", "Users (now)", "Users (2030)"],
               rows, [7, 26, 16, 10, 15, 22, 9, 12, 12, 12],
               note="Enterprise 10.0.0.0/8 and 2001:db8:a000::/40 (documentation prefix used for the lab). "
                    "Each site is advertised to the overlay as exactly one /16 and one /48.")
last = r0 + len(rows)
ws.cell(last + 1, 1, "Total").font = Font(name=FONT, bold=True)
for col in ("E", "I", "J"):
    c = ws[f"{col}{last + 1}"]
    c.value = f"=SUM({col}{r0 + 1}:{col}{last})"
    c.font = Font(name=FONT, bold=True)
for row in ws.iter_rows(min_row=r0 + 1, max_row=last + 1):
    for c in row:
        if c.column in (5, 9, 10):
            c.number_format = "#,##0"

# ---- 2. VLSM pools
rows = []
for site, v, p, need, note in sot.POOLS:
    n = ip.ip_network(p)
    rows.append([site, v if isinstance(v, int) else "-", vname(v), p, n.prefixlen,
                 "=2^(32-E{r})-2", need if need else None,
                 '=IF(G{r}="","",G{r}/F{r})', '=IF(G{r}="","",F{r}-G{r})', note])
ws, r0 = sheet(wb, "IPv4 VLSM Pools",
               ["Site", "VLAN", "Function", "Pool prefix", "Len", "Usable hosts", "Demand 2030",
                "Utilisation", "Headroom", "Notes"],
               rows, [7, 7, 18, 17, 6, 13, 13, 11, 11, 56],
               note="Pools allocated largest-first per site (VLSM). Each pool is carved into /24 access blocks "
                    "(max 254 hosts per broadcast domain). Demand 2030 = hosts expected by 2030 (assumption, see report Sec. 3).")
for row in ws.iter_rows(min_row=r0 + 1, max_row=r0 + len(rows)):
    row[5].number_format = "#,##0"
    row[6].number_format = "#,##0"
    row[6].font = Font(name=FONT, size=10, color="0000FF")
    row[7].number_format = "0.0%"
    row[8].number_format = "#,##0"

# ---- 3. Deployed subnets (lab)
rows = []
for site, subs in sot.SUBNETS.items():
    ga, gb = sot.GATEWAYS[site]
    for s in subs:
        n = ip.ip_network(s["v4"])
        a = "A" if s["active"] == "A" else "B"
        rows.append([site, s["vlan"], sot.VLANS[s["vlan"]], s["v4"], str(n.netmask), sot.nth(s["v4"], 1),
                     f"{ga} {sot.nth(s['v4'], 2)}", f"{gb} {sot.nth(s['v4'], 3)}",
                     ga if a == "A" else gb, s["v6"] or "IPv4 only (guest)",
                     "Yes (relay -> 10.10.43.10)" if s.get("dhcp") else "Static",
                     ", ".join(x for x in (s.get("acl_in"), s.get("acl_out")) if x) or "-"])
sheet(wb, "Deployed Subnets",
      ["Site", "VLAN", "Name", "IPv4 subnet", "Mask", "HSRP VIP", "Gateway A (.2)", "Gateway B (.3)",
       "HSRP active", "IPv6 /64 (VIP fe80::1)", "Addressing", "ACL"],
      rows, [7, 7, 17, 16, 15, 13, 24, 24, 13, 26, 24, 26],
      note="Subnets configured in the lab = first /24 of each pool. HSRPv2 VIP .1 (IPv4) / FE80::1 (IPv6).")

# ---- 4. IPv6 hierarchy
rows = [["ENT", "2001:db8:a000::/40", "Enterprise allocation (256 x /48)", ""],
        ["WAN", sot.WAN_OVERLAY_V6, "Overlay tunnels: 2001:db8:a000:<tunnel#>::/64", ""]]
for k, s in sot.SITES.items():
    rows.append([k, s["v6"], f"{s['name']} -- 65,536 x /64", ""])
    rows.append([k, s["v6"].replace("::/48", ":VVBB::/64"), "LAN: VV = VLAN ID digits, BB = access block (01..99)",
                 f"e.g. VLAN 20 block 01 -> {s['v6'].replace('::/48', ':2001::/64')}"])
    rows.append([k, s["v6"].replace("::/48", ":fe00::/56"), "Point-to-point links (/64 each)", ""])
    rows.append([k, s["v6"].replace("::/48", ":ff00::/64"), "Loopbacks (/128): ...:ff00::<IPv4 last octet>", ""])
sheet(wb, "IPv6 Plan", ["Scope", "Prefix", "Use", "Example"], rows, [7, 30, 52, 44])

# ---- 5. Links & tunnels
rows = []
for site, a, aif, b, bif, v4, v6 in sot.P2P_LINKS:
    rows.append([site, "Routed P2P", f"{a} {aif}", sot.nth(v4, 1), f"{b} {bif}", sot.nth(v4, 2), v4, v6])
for isp, iif, ce, cif, net in sot.ISP_LINKS:
    rows.append(["WAN", "ISP access (demarc)", f"{isp} {iif}", sot.nth(net, 1), f"{ce} {cif}", sot.nth(net, 2), net, "-"])
a, aif, b, bif, net = sot.ISP_PEERING
rows.append(["WAN", "ISP peering", f"{a} {aif}", sot.nth(net, 1), f"{b} {bif}", sot.nth(net, 2), net, "-"])
for num, a, b, v4, v6, plane in sot.TUNNELS:
    rows.append(["WAN", f"Tunnel{num} plane {plane}", a, sot.nth(v4, 1), b, sot.nth(v4, 2), v4, v6])
sheet(wb, "Links & Tunnels", ["Site", "Type", "Side A", "IP A", "Side B", "IP B", "IPv4", "IPv6"],
      rows, [7, 20, 22, 15, 22, 15, 17, 26])

# ---- 6. Loopbacks & management
rows = []
for n, d in sot.DEVICES.items():
    lo6 = sot.lo0_v6(n) if d.get("lo0") and d["lab"] == "A" and d["role"] not in ("isp",) else "-"
    rows.append([d["site"], n, d["platform"], d["role"], d.get("lo0", "-"), lo6, d["mgmt"],
                 d.get("svi99", d.get("ip", "-")), "DC fabric" if d["lab"] == "B" else "Campus/WAN", sot.RAM_MB[d["platform"]]])
ws, r0 = sheet(wb, "Loopbacks & Mgmt",
               ["Site", "Device", "Image", "Role", "Loopback0", "Loopback0 IPv6", "OOB mgmt (Gi0/0)",
                "In-band / host IP", "Part", "RAM (MB)"],
               rows, [7, 13, 9, 9, 16, 26, 17, 17, 12, 10])
last = r0 + len(rows)
ws.cell(last + 1, 8, "Total node RAM (MB)").font = Font(name=FONT, bold=True)
ws.cell(last + 1, 10, f'=SUM(J{r0 + 1}:J{last})').font = Font(name=FONT, bold=True)

wb.save(os.path.join(OUT, "TVI_IP_Plan.xlsx"))

# ---------------------------------------------------------------- Markdown
md = ["# TVI IP Addressing Plan", "",
      "Generated from `tools/sot.py`. The Excel workbook `TVI_IP_Plan.xlsx` has the same data with formulas.", "",
      "## Site summaries", "", "| Site | IPv4 | IPv6 | BGP AS | OSPF |", "|---|---|---|---|---|"]
for k, s in sot.SITES.items():
    md.append(f"| {k} | {s['v4']} | {s['v6']} | {s['asn']} | {s['ospf']} |")
md += ["", "## IPv4 VLSM pools (2030 sizing)", "", "| Site | VLAN | Function | Pool | Usable | Demand 2030 |",
       "|---|---|---|---|---|---|"]
for site, v, p, need, note in sot.POOLS:
    md.append(f"| {site} | {v} | {vname(v)} | {p} | {ip.ip_network(p).num_addresses - 2:,} | {need or '-'} |")
md += ["", "## Deployed subnets (lab)", "", "| Site | VLAN | Name | IPv4 | VIP | IPv6 |", "|---|---|---|---|---|---|"]
for site, subs in sot.SUBNETS.items():
    for s in subs:
        md.append(f"| {site} | {s['vlan']} | {sot.VLANS[s['vlan']]} | {s['v4']} | {sot.nth(s['v4'], 1)} | {s['v6'] or '-'} |")
md += ["", "## Links and tunnels", "", "| Type | A | IP A | B | IP B | Subnet |", "|---|---|---|---|---|---|"]
for site, a, aif, b, bif, v4, v6 in sot.P2P_LINKS:
    md.append(f"| P2P | {a} {aif} | {sot.nth(v4, 1)} | {b} {bif} | {sot.nth(v4, 2)} | {v4} |")
for isp, iif, ce, cif, net in sot.ISP_LINKS:
    md.append(f"| ISP | {isp} {iif} | {sot.nth(net, 1)} | {ce} {cif} | {sot.nth(net, 2)} | {net} |")
for num, a, b, v4, v6, plane in sot.TUNNELS:
    md.append(f"| Tunnel{num} ({plane}) | {a} | {sot.nth(v4, 1)} | {b} | {sot.nth(v4, 2)} | {v4} |")
md += ["", "## Devices", "", "| Device | Role | Loopback0 | OOB mgmt |", "|---|---|---|---|"]
for n, d in sot.DEVICES.items():
    md.append(f"| {n} | {d['role']} | {d.get('lo0', '-')} | {d['mgmt']} |")
open(os.path.join(OUT, "ip_plan.md"), "w").write("\n".join(md) + "\n")
print("wrote ip-plan/TVI_IP_Plan.xlsx and ip-plan/ip_plan.md")
