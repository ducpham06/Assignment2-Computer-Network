# Verification test plan

Run top to bottom; each block depends on the one above. Paste every output into the matching
**Evidence** box in the report (`report/main.tex`, Section 7) — screenshots must come from your own lab.

## Step 3 — Layer 2

| ID | Device | Command | Pass if |
|---|---|---|---|
| T01 | HCM-CORE1 | `show interfaces trunk` | Po1 + Gi0/3 trunking, native 999, allowed lists as designed |
| T02 | HCM-CORE1 | `show etherchannel summary` | `Po1(SU)` with `Gi0/1(P) Gi0/2(P)` |
| T03 | HCM-ACC1 | `show spanning-tree root` | VLAN 10/12/40/80 root = CORE1 MAC, VLAN 60/70/99 root = CORE2 MAC |
| T03b | HCM-ACC1 | `show spanning-tree vlan 10` | Gi0/1 Root FWD, Gi0/2 Altn BLK |

## Step 4 — FHRP & IP services

| ID | Device | Command | Pass if |
|---|---|---|---|
| T04 | HCM-CORE1, HAN-EDG1 | `show standby brief` | CORE1 Active for 10/12/40/80, Standby for 60/70/99; HAN-EDG1 Active 20/99 |
| T05 | PC-HAN-ENG | `ip dhcp` then `show ip` | 10.20.0.21+ /24, GW 10.20.0.1, DNS 10.10.43.10 |
| T05b | HCM-SRV1 | `show ip dhcp binding` | bindings from all three sites |
| T06 | PC-HCM-CORP | `ping hcm-edg1.tvi.lab` | resolves to 10.10.255.1 |

## Step 5 — OSPF underlay

| ID | Device | Command | Pass if |
|---|---|---|---|
| T07 | HCM-CORE1 | `show ip ospf neighbor` / `show ipv6 ospf neighbor` | 3 x FULL (EDG1, EDG2, CORE2) |
| T07b | HAN-EDG1 | `show ip ospf neighbor` | 1 x FULL (HAN-EDG2) |
| T08 | HCM-CORE1 | `ping 10.10.255.1 source lo0` (and .2 .4) | 100 % |

## Step 6 — BGP overlay & WAN

| ID | Device | Command | Pass if |
|---|---|---|---|
| T09 | HCM-EDG1 | `show bgp ipv4 unicast summary` | 203.0.113.1, 10.10.255.2, 10.0.0.2, 10.0.0.6 all with a prefix count |
| T09b | HCM-EDG1 | `show bgp ipv6 unicast summary` | 3 IPv6 sessions up |
| T10 | HCM-EDG1 | `show crypto ikev2 sa` / `show crypto ipsec sa \| i encaps\|decaps` | 2 SAs READY, counters rising |
| T11 | HCM-EDG1 | `show ip route bgp` | 10.20.0.0/16 via 10.0.0.2, 10.30.0.0/16 via 10.0.0.6, 0.0.0.0/0 via 203.0.113.1 |
| T12 | HCM-CORE1 | `show ip route ospf` | `O*E2 0.0.0.0/0` and `O E2 10.20.0.0/16`, `10.30.0.0/16` via both edges |

## Step 6b — DC fabric (EVPN-VXLAN) and border

| ID | Device | Command | Pass if |
|---|---|---|---|
| T24 | DC-LEAF1 | `show bgp evpn summary` | 2 peers (both spines) Estab |
| T24b | DC-LEAF1 | `show vxlan vtep` | remote VTEP 10.10.191.22 |
| T24c | DC-H1 | `ping 10.10.128.12` / `ping 10.10.129.13` | success (L2VNI / L3VNI) |
| T24d | DC-H1 | `ping <PC-HAN-ENG IP>` | success (leaf -> core -> overlay -> Hanoi) |
| T24e | HCM-CORE1 | `show ip route ospf \| i 10.10.12` | 10.10.128.0/24 and 10.10.129.0/24 learned from the leaves |

## Step 7 — Security

| ID | Device | Command | Pass if |
|---|---|---|---|
| T16 | PC-HAN-ENG | `ping 192.0.2.10` | success |
| T16b | HAN-EDG1 | `show ip nat translations` | inside 10.20.0.x -> outside 203.0.113.6 (local breakout, not HQ) |
| T17 | PC-HCM-GUEST | `ping 10.10.43.10` / `ping 192.0.2.10` | fail / success |
| T18 | PC-DAD-IOT | `ping 10.30.128.21` / `ping 10.10.43.10` | fail / success |
| T19 | PC-HAN-ENG -> PC-HCM-EXEC | `ping <exec IP>` | fail; the reverse direction succeeds |
| T19b | HCM-CORE1 | `show access-lists ACL-EXEC-PROTECT` | deny counter increments |
| T20 | DAD-ACC1 | `show ip dhcp snooping binding`, `show ip arp inspection statistics` | bindings present, DAI counters |
| T21 | HAN-EDG1 | `show policy-map type inspect zone-pair sessions` | inspected sessions from T16 |

## Step 8 — QoS

| ID | Device | Command | Pass if |
|---|---|---|---|
| T22 | HCM-EDG1 / EDG2 | `show policy-map interface Gi0/1` | `CM-WAN-VOICE` packets > 0, queue stats |
| T22b | HCM-SRV1 | `show ip sla statistics` | return code OK, RTT, jitter, MOS |

## Step 10 — End-to-end

| ID | From | Command | Pass if |
|---|---|---|---|
| T13 | PC-HAN-ENG | `trace <PC-HCM-CORP IP>` | 10.20.0.2 -> 10.0.0.1 -> 10.10.254.x -> host |
| T14 | PC-HAN-ENG | `trace <PC-DAD-LOG IP>` | second hop 10.0.0.18 (direct Tunnel13, not via HQ) |
| T15 | PC-HAN-ENG | `ping 2001:db8:a010:1201::<host>` | success |

## Failover

Start `ping <target> -t` on the VPCS, perform the action, count lost replies, restore.

| ID | Action | Traffic | Expect |
|---|---|---|---|
| F1 | HCM-CORE1 `int gi0/1` `shutdown` | PC-HCM-EXEC -> HCM-SRV1 | 0 lost |
| F2 | HCM-CORE1 `int gi1/0` `shutdown` | PC-HCM-CORP -> PC-HAN-ENG | <=1 lost |
| F3 | Stop node HCM-CORE1 | PC-HCM-CORP -> PC-DAD-LOG | <=4 lost, CORE2 Active |
| F4 | HAN-EDG1 `int gi0/1` `shutdown` | PC-HAN-ENG -> PC-HCM-CORP and 192.0.2.10 | <=15 lost, then via plane B |
| F5 | Stop node HAN-EDG1 | PC-HAN-ENG -> PC-HCM-CORP | <=4 lost |
