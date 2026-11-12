# EVE-NG build guide

Generated from `tools/sot.py` -- the cabling below is exactly what the configs expect.

## 0. Host sizing

Reference host: Intel Core Ultra 5 125H (14 cores / 18 threads), 32 GB RAM.

* Give the EVE-NG VM **24 GB RAM** and **12 vCPUs**; enable *Virtualize Intel VT-x/EPT* (nested virtualisation).
* The whole topology (campus/WAN + DC fabric) needs about 11.5 GB of node RAM, so everything runs in **one** EVE-NG lab at the same time.
* Plug the laptop into mains power and use the *Performance* power mode during the demo (the hybrid P/E cores throttle on battery).
* Start nodes in batches of 3-5: ISPs -> edges -> cores -> access -> server -> spines -> leaves -> VPCS.

## 1. Images

| Template | Settings |
|---|---|
| vios | Cisco vIOS `vios-adventerprisek9-m.SPA.159-3.M6` (extract the `.tgz` into `/opt/unetlab/addons/qemu/`), 512 MB, **6 Ethernets** |
| viosl2 | Cisco vIOS-L2 `viosl2-adventerprisek9-m.ssa.high_iron_20200929` (extract the `.tgz` the same way), 1024 MB, 4 Ethernet groups (16 ports) |
| VPCS | built-in |

## 2. Management network

1. Add a **Network** object of type *Management(Cloud0)*.
2. Connect **Gi0/0** of every node to it.
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
| DC-SPINE1 | vios | spine | 172.16.99.41 |
| DC-SPINE2 | vios | spine | 172.16.99.42 |
| DC-LEAF1 | vios | leaf | 172.16.99.43 |
| DC-LEAF2 | vios | leaf | 172.16.99.44 |
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
| DC-H1 | VPCS | DC host, TENANT-PROD | -- |
| DC-H2 | VPCS | DC host, TENANT-PROD | -- |
| DC-H3 | VPCS | DC host, TENANT-DEV | -- |
| DC-H4 | VPCS | DC host, TENANT-DEV | -- |

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
| 35 | HCM-CORE1 | Gi1/2 | DC-LEAF1 | Gi0/5 | DC border 10.10.189.0/30 |
| 36 | HCM-CORE2 | Gi1/2 | DC-LEAF2 | Gi0/5 | DC border 10.10.189.4/30 |
| 37 | DC-SPINE1 | Gi0/1 | DC-LEAF1 | Gi0/1 | fabric 10.10.190.0/30 |
| 38 | DC-SPINE1 | Gi0/2 | DC-LEAF2 | Gi0/1 | fabric 10.10.190.4/30 |
| 39 | DC-SPINE2 | Gi0/1 | DC-LEAF1 | Gi0/2 | fabric 10.10.190.8/30 |
| 40 | DC-SPINE2 | Gi0/2 | DC-LEAF2 | Gi0/2 | fabric 10.10.190.12/30 |
| 41 | DC-LEAF1 | Gi0/3 | DC-H1 | eth0 | DC host TENANT-PROD 10.10.128.0/24 |
| 42 | DC-LEAF2 | Gi0/3 | DC-H2 | eth0 | DC host TENANT-PROD 10.10.129.0/24 |
| 43 | DC-LEAF1 | Gi0/4 | DC-H3 | eth0 | DC host TENANT-DEV 10.10.130.0/24 |
| 44 | DC-LEAF2 | Gi0/4 | DC-H4 | eth0 | DC host TENANT-DEV 10.10.131.0/24 |

Plus Gi0/0 of all 18 Cisco nodes to Cloud0.

## 5. Configure

1. Console into each node, `enable`, `configure terminal`, paste `configs/labA/<NODE>.cfg`, then `end` and `write memory`.
   * IOSvL2 may print `%Warning` lines for features it ignores; check for `% Invalid input` and report them.
   * The RSA key line takes a few seconds -- wait for the prompt before the rest of the paste continues.
2. DC fabric nodes are vIOS too: paste `configs/labB/<NODE>.cfg` the same way.
3. On each VPCS, paste `configs/vpcs/<NODE>.vpc` and `save`.
4. Wait ~60 s, then run the checks in `docs/test-plan.md`.

## 6. DC fabric checks

`show mpls ldp neighbor`, `show bgp vpnv4 unicast all summary`, `show ip route vrf TENANT-PROD` on the leaves; ping DC-H1 -> DC-H2 (PROD across the fabric), DC-H3 -> DC-H4 (DEV), DC-H1 -> DC-H3 (must FAIL: tenant isolation) and DC-H1 -> PC-HAN-ENG (border + WAN overlay). On HCM-CORE1: `show ip route ospf | i 10.10.12` shows the DC tenant subnets learned from the leaves.
