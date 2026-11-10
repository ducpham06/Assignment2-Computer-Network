# TVI Innovations — Large Enterprise Network (Assignment 2)

Design, configurations, automation and report for the TechViet Innovations three-site network
(HCM HQ + data centre, Hanoi R&D, Da Nang logistics), built for **EVE-NG** on a 12 GB machine.

## What is in here

| Path | Content | Rubric step |
|---|---|---|
| `report/main.pdf` (`main.tex`) | Technical Explanation Report (LaTeX). Yellow **Evidence** boxes must be filled with your own lab outputs | 10 |
| `diagrams/*.drawio` (+ `.pdf/.png/.svg`) | Logical, physical, routing, HCM L2/L3, DC fabric diagrams — open the `.drawio` in diagrams.net to edit | 1 |
| `ip-plan/TVI_IP_Plan.xlsx`, `ip_plan.md` | VLSM IPv4 + hierarchical IPv6 plan | 2 |
| `configs/labA/*.cfg` | 14 paste-ready configs (vIOS / IOSvL2): VLANs, LACP, RSTP, HSRPv2, DHCP relay, OSPFv2/v3, BGP, GRE/IPsec, ZBF, NAT, ACLs, DHCP snooping/DAI, QoS | 3–8 |
| `configs/labB/*.cfg` | 4 Arista vEOS configs: EVPN-VXLAN spine-leaf | 6 |
| `configs/vpcs/*.vpc` | VPCS host settings | — |
| `automation/` | Python/Netmiko: inventory, getpass/env credentials, baseline + VLAN push, backups, diff, compliance, telemetry, tests | 9 |
| `docs/eve-ng-build-guide.md` | Node list + full cabling table + build order | — |
| `docs/test-plan.md`, `docs/demo-runbook.md` | Verification/failover commands with pass criteria; 15-minute demo script | 10 |
| `tools/` | **Source of truth** (`sot.py`) and the renderers/validator that produce everything above | 9 |

## Two labs (RAM)

* **Lab A** — campus + WAN, 14 Cisco nodes + 10 VPCS, ≈ 8.2 GB.
* **Lab B** — EVPN-VXLAN fabric, 3–4 vEOS + 3 VPCS, 6–8 GB. Run it with Lab A stopped.

## Regenerate everything after changing the design

```bash
pip install --break-system-packages openpyxl pyyaml netmiko pytest   # or use a venv
./build.sh        # renders configs, validates them, rebuilds IP plan, inventory, diagrams, docs, report
```

`tools/validate.py` runs 17 consistency checks on the rendered configs (duplicate IPs, link subnets,
tunnel symmetry, BGP neighbour/AS symmetry, HSRP/STP alignment, VLANs on trunks, DHCP pools,
undefined ACLs/policies, RAM budget). It does **not** prove IOS accepts every line — the lab does.

## Credentials

Lab device login: `tviadmin` / `Tvi@Lab2026` (set in the configs; change it in `tools/build_configs.py`).
The automation never stores it: export `TVI_SSH_USER`/`TVI_SSH_PASS` or answer the prompt.
