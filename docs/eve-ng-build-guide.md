# EVE-NG build guide

Generated from `tools/sot.py` -- the cabling below is exactly what the configs expect.

## 0. Host sizing

Reference host: Intel Core Ultra 5 125H (14 cores / 18 threads), 32 GB RAM.

* Give the EVE-NG VM **24 GB RAM** and **12 vCPUs**; enable *Virtualize Intel VT-x/EPT* (nested virtualisation).
* The whole topology (campus/WAN + DC fabric) needs about 16.2 GB of node RAM, so everything runs in **one** EVE-NG lab at the same time.
* Plug the laptop into mains power and use the *Performance* power mode during the demo (the hybrid P/E cores throttle on battery).
* Start nodes in batches of 3-5: ISPs -> edges -> cores -> access -> server -> spines -> leaves -> VPCS.

## 1. Images

| Template | Settings |
|---|---|
| vios | Cisco vIOS (vios-adventerprisek9-m), 512 MB, **6 Ethernets** |
| viosl2 | Cisco IOSvL2, 768 MB, 4 Ethernet groups (16 ports) |
| veos | Arista vEOS-lab, 2048 MB, 4+ Ethernets |
| VPCS | built-in |

## 2. Management network

1. Add a **Network** object of type *Management(Cloud0)*.
2. Connect **Gi0/0** of every Cisco node (Management1 on vEOS) to it.
3. On the EVE-NG VM shell: `ip addr add 172.16.99.1/24 dev pnet0` (add it to `/etc/network/interfaces` to keep it after reboot).
4. Test from the EVE VM: `ping 172.16.99.11` once HCM-EDG1 is configured.

## 3. Nodes

| Node | Template | Role | OOB mgmt |
|---|---|---|---|
| ISP-A | vios | isp | 172.16.99.101 |
| ISP-B | vios | isp | 172.16.99.102 |
| HCM-EDG1 | vios | edge | 172.16.99.11 |
| HCM-EDG2 | vios | edge | 172.16.99.12 |
| HCM-CORE1 | viosl2 | core | 172.16.99.13 |
| HCM-CORE2 | viosl2 | core | 172.16.99.14 |
| HCM-ACC1 | viosl2 | access | 172.16.99.15 |
| HCM-SRV1 | vios | server | 172.16.99.16 |
| HAN-EDG1 | vios | edge | 172.16.99.21 |
| HAN-EDG2 | vios | edge | 172.16.99.22 |
| HAN-ACC1 | viosl2 | access | 172.16.99.25 |
| DAD-EDG1 | vios | edge | 172.16.99.31 |
| DAD-EDG2 | vios | edge | 172.16.99.32 |
| DAD-ACC1 | viosl2 | access | 172.16.99.35 |
| DC-SPINE1 | veos | spine | 172.16.99.41 |
| DC-SPINE2 | veos | spine | 172.16.99.42 |
| DC-LEAF1 | veos | leaf | 172.16.99.43 |
| DC-LEAF2 | veos | leaf | 172.16.99.44 |
| PC-HCM-EXEC | VPCS | host VLAN 10 | -- |
| PC-HCM-CORP | VPCS | host VLAN 12 | -- |
| PC-HCM-GUEST | VPCS | host VLAN 60 | -- |
| PC-HCM-PHONE | VPCS | host VLAN 40 | -- |
| PC-HAN-ENG | VPCS | host VLAN 20 | -- |
| PC-HAN-PHONE | VPCS | host VLAN 40 | -- |
| PC-HAN-GUEST | VPCS | host VLAN 60 | -- |
| PC-DAD-LOG | VPCS | host VLAN 30 | -- |
| PC-DAD-IOT | VPCS | host VLAN 50 | -- |
| PC-DAD-PHONE | VPCS | host VLAN 40 | -- |
| PC-DAD-GUEST | VPCS | host VLAN 60 | -- |
| DC-H1 | VPCS | DC host VLAN 110 | -- |
| DC-H2 | VPCS | DC host VLAN 110 | -- |
| DC-H3 | VPCS | DC host VLAN 120 | -- |

## 4. Cabling

| # | From | Port | To | Port | Purpose |
|---|---|---|---|---|---|
| 1 | ISP-A | Gi0/1 | HCM-EDG1 | Gi0/1 | carrier access 203.0.113.0/30 |
| 2 | ISP-A | Gi0/2 | HAN-EDG1 | Gi0/1 | carrier access 203.0.113.4/30 |
| 3 | ISP-A | Gi0/3 | DAD-EDG1 | Gi0/1 | carrier access 203.0.113.8/30 |
| 4 | ISP-B | Gi0/1 | HCM-EDG2 | Gi0/1 | carrier access 198.51.100.0/30 |
| 5 | ISP-B | Gi0/2 | HAN-EDG2 | Gi0/1 | carrier access 198.51.100.4/30 |
| 6 | ISP-B | Gi0/3 | DAD-EDG2 | Gi0/1 | carrier access 198.51.100.8/30 |
| 7 | ISP-A | Gi0/4 | ISP-B | Gi0/4 | ISP peering 203.0.113.248/30 |
| 8 | HCM-EDG1 | Gi0/2 | HCM-CORE1 | Gi1/0 | routed 10.10.254.0/30 |
| 9 | HCM-EDG1 | Gi0/3 | HCM-CORE2 | Gi1/0 | routed 10.10.254.4/30 |
| 10 | HCM-EDG2 | Gi0/2 | HCM-CORE1 | Gi1/1 | routed 10.10.254.8/30 |
| 11 | HCM-EDG2 | Gi0/3 | HCM-CORE2 | Gi1/1 | routed 10.10.254.12/30 |
| 12 | HCM-EDG1 | Gi0/4 | HCM-EDG2 | Gi0/4 | routed 10.10.254.16/30 |
| 13 | HAN-EDG1 | Gi0/3 | HAN-EDG2 | Gi0/3 | routed 10.20.254.0/30 |
| 14 | DAD-EDG1 | Gi0/3 | DAD-EDG2 | Gi0/3 | routed 10.30.254.0/30 |
| 15 | HCM-CORE1 | Gi0/1 | HCM-CORE2 | Gi0/1 | 802.1Q trunk (Po1 LACP member) |
| 16 | HCM-CORE1 | Gi0/2 | HCM-CORE2 | Gi0/2 | 802.1Q trunk (Po1 LACP member) |
| 17 | HCM-CORE1 | Gi0/3 | HCM-ACC1 | Gi0/1 | 802.1Q trunk |
| 18 | HCM-CORE2 | Gi0/3 | HCM-ACC1 | Gi0/2 | 802.1Q trunk |
| 19 | HAN-EDG1 | Gi0/2 | HAN-ACC1 | Gi0/1 | 802.1Q trunk |
| 20 | HAN-EDG2 | Gi0/2 | HAN-ACC1 | Gi0/2 | 802.1Q trunk |
| 21 | DAD-EDG1 | Gi0/2 | DAD-ACC1 | Gi0/1 | 802.1Q trunk |
| 22 | DAD-EDG2 | Gi0/2 | DAD-ACC1 | Gi0/2 | 802.1Q trunk |
| 23 | HCM-ACC1 | Gi1/0 | PC-HCM-EXEC | eth0 | access VLAN 10 |
| 24 | HCM-ACC1 | Gi1/1 | PC-HCM-CORP | eth0 | access VLAN 12 |
| 25 | HCM-ACC1 | Gi1/2 | PC-HCM-GUEST | eth0 | access VLAN 60 |
| 26 | HCM-ACC1 | Gi1/3 | PC-HCM-PHONE | eth0 | access VLAN 40 |
| 27 | HCM-ACC1 | Gi2/0 | HCM-SRV1 | Gi0/1 | access VLAN 80 |
| 28 | HAN-ACC1 | Gi1/0 | PC-HAN-ENG | eth0 | access VLAN 20 |
| 29 | HAN-ACC1 | Gi1/1 | PC-HAN-PHONE | eth0 | access VLAN 40 |
| 30 | HAN-ACC1 | Gi1/2 | PC-HAN-GUEST | eth0 | access VLAN 60 |
| 31 | DAD-ACC1 | Gi1/0 | PC-DAD-LOG | eth0 | access VLAN 30 |
| 32 | DAD-ACC1 | Gi1/1 | PC-DAD-IOT | eth0 | access VLAN 50 |
| 33 | DAD-ACC1 | Gi1/2 | PC-DAD-PHONE | eth0 | access VLAN 40 |
| 34 | DAD-ACC1 | Gi1/3 | PC-DAD-GUEST | eth0 | access VLAN 60 |
| 35 | HCM-CORE1 | Gi1/2 | DC-LEAF1 | Ethernet5 | DC border 10.10.189.0/30 |
| 36 | HCM-CORE2 | Gi1/2 | DC-LEAF2 | Ethernet5 | DC border 10.10.189.4/30 |
| 37 | DC-SPINE1 | Ethernet1 | DC-LEAF1 | Ethernet1 | fabric 10.10.190.0/31 |
| 38 | DC-SPINE1 | Ethernet2 | DC-LEAF2 | Ethernet1 | fabric 10.10.190.2/31 |
| 39 | DC-SPINE2 | Ethernet1 | DC-LEAF1 | Ethernet2 | fabric 10.10.190.4/31 |
| 40 | DC-SPINE2 | Ethernet2 | DC-LEAF2 | Ethernet2 | fabric 10.10.190.6/31 |
| 41 | DC-LEAF1 | Ethernet3 | DC-H1 | eth0 | DC host VLAN 110 |
| 42 | DC-LEAF2 | Ethernet3 | DC-H2 | eth0 | DC host VLAN 110 |
| 43 | DC-LEAF2 | Ethernet4 | DC-H3 | eth0 | DC host VLAN 120 |

Plus Gi0/0 of all 14 Cisco nodes and Management1 of the 4 vEOS nodes to Cloud0.

## 5. Configure

1. Console into each node, `enable`, `configure terminal`, paste `configs/labA/<NODE>.cfg`, then `end` and `write memory`.
   * IOSvL2 may print `%Warning` lines for features it ignores; check for `% Invalid input` and report them.
   * The RSA key line takes a few seconds -- wait for the prompt before the rest of the paste continues.
2. vEOS: log in as `admin` (no password), `enable`, `configure`, paste `configs/labB/<NODE>.cfg`, `write`, then `reload` once (multi-agent routing model).
3. On each VPCS, paste `configs/vpcs/<NODE>.vpc` and `save`.
4. Wait ~60 s, then run the checks in `docs/test-plan.md`.

## 6. DC fabric checks

`show bgp evpn summary`, `show vxlan vtep`, `show bgp evpn route-type mac-ip` on the leaves; ping DC-H1 -> DC-H2 (L2VNI), DC-H1 -> DC-H3 (L3VNI) and DC-H1 -> PC-HAN-ENG (border + WAN overlay). On HCM-CORE1: `show ip route ospf | i 10.10.12` shows the DC tenant subnets learned from the leaves.
