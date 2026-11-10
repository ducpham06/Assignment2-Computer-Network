#!/usr/bin/env python3
"""
Render every device configuration from the Source of Truth (tools/sot.py).

    python3 tools/build_configs.py            -> configs/labA/*.cfg, configs/labB/*.cfg

Day-0 configs contain everything needed for the network to work. The Day-1
baseline (banner, NTP, syslog, login hardening) and the standard VLAN set are
deliberately left to the automation in automation/ so that Step 9 has real
work to do and its pre/post diff is meaningful.
"""
import ipaddress as ip
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sot import *  # noqa: F401,F403

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB_PASSWORD = "Tvi@Lab2026"     # lab-only device credential (hashed by IOS on entry)
LAB_USER = "tviadmin"
IKE_PSK = "TVI-Overlay-PSK-2026"

# --------------------------------------------------------------------------
# generic helpers
# --------------------------------------------------------------------------

def gw_role(site, dev):
    a, b = GATEWAYS[site]
    return "A" if dev == a else "B" if dev == b else None


def gw_addr(prefix, role):
    """VIP = .1 / ::1 is replaced by FE80::1 for v6; A = .2, B = .3"""
    return nth(prefix, 2 if role == "A" else 3)


def site_vlans(site):
    return [s["vlan"] for s in SUBNETS[site]]


def p2p_ends(dev):
    """Yield (local-if, local v4, prefixlen, local v6, peer, peer-if) for routed links."""
    for site, a, aif, b, bif, v4, v6 in P2P_LINKS:
        if dev == a:
            yield aif, nth(v4, 1), v4, nth(v6, 1), b, bif
        elif dev == b:
            yield bif, nth(v4, 2), v4, nth(v6, 2), a, aif


def isp_link(dev):
    for isp, iif, ce, cif, net in ISP_LINKS:
        if dev == ce:
            return dict(isp=isp, isp_if=iif, ce_if=cif, net=net, ce_ip=nth(net, 2), isp_ip=nth(net, 1))
    return None


def tunnels_of(dev):
    for num, a, b, v4, v6, plane in TUNNELS:
        if dev == a:
            yield dict(num=num, peer=b, ip=nth(v4, 1), peer_ip=nth(v4, 2), v4=v4,
                       ip6=nth(v6, 1), peer_ip6=nth(v6, 2), plane=plane)
        elif dev == b:
            yield dict(num=num, peer=a, ip=nth(v4, 2), peer_ip=nth(v4, 1), v4=v4,
                       ip6=nth(v6, 2), peer_ip6=nth(v6, 1), plane=plane)


def trunks_of(dev):
    for a, aif, b, bif, po in TRUNKS:
        if dev == a:
            yield aif, b, bif, po
        elif dev == b:
            yield bif, a, aif, po


def banner(dev, d):
    return [
        "!" + "=" * 74,
        f"! TechViet Innovations (TVI) -- {dev}",
        f"! Platform: {d['platform']}   Role: {d['role']}   Site: {d['site']}",
        "! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.",
        "! Paste into the device in global configuration mode (conf t).",
        "!" + "=" * 74,
    ]


def ios_common(dev, d, routing=True, v6=True, dns_lookup=False):
    L = banner(dev, d) + [
        f"hostname {dev}",
        "!",
        "service timestamps debug datetime msec localtime show-timezone",
        "service timestamps log datetime msec localtime show-timezone",
        "service password-encryption",
        "clock timezone ICT 7 0",
        "!",
        f"ip domain name {DOMAIN}",
        "ip domain lookup" if dns_lookup else "no ip domain lookup",
    ]
    if routing:
        L += ["ip cef"]
    if v6:
        L += ["ipv6 unicast-routing", "ipv6 cef"]
    L += [
        "!",
        f"username {LAB_USER} privilege 15 secret {LAB_PASSWORD}",
        f"enable secret {LAB_PASSWORD}",
        "aaa new-model",
        "aaa authentication login default local",
        "aaa authentication login CONSOLE none",
        "aaa authorization exec default local",
        "!",
        "crypto key generate rsa modulus 2048",
        "ip ssh version 2",
        "ip ssh time-out 60",
        "ip ssh authentication-retries 3",
        "!",
    ]
    return L


def mgmt_if(d, l2=False):
    L = ["interface GigabitEthernet0/0",
         " description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)"]
    if l2:
        L.append(" no switchport")
    L += [f" ip address {d['mgmt']} {mask(MGMT_NET)}",
          " no cdp enable",
          " no shutdown",
          "!"]
    return L


def vty_block():
    return [
        "ip access-list standard ACL-MGMT-VTY",
        " remark SSH only from OOB network and the three in-band MGMT VLANs",
        f" permit {ip.ip_network(MGMT_NET).network_address} {wildcard(MGMT_NET)}",
        f" permit {site_subnet('HCM', 99)['v4'].split('/')[0]} {wildcard(site_subnet('HCM', 99)['v4'])}",
        f" permit {site_subnet('HAN', 99)['v4'].split('/')[0]} {wildcard(site_subnet('HAN', 99)['v4'])}",
        f" permit {site_subnet('DAD', 99)['v4'].split('/')[0]} {wildcard(site_subnet('DAD', 99)['v4'])}",
        " deny   any log",
        "!",
        "line con 0",
        " login authentication CONSOLE",
        " logging synchronous",
        " exec-timeout 0 0",
        " transport preferred none",
        "line vty 0 4",
        " access-class ACL-MGMT-VTY in",
        " transport input ssh",
        " transport preferred none",
        " exec-timeout 15 0",
        " logging synchronous",
        "!",
    ]


def end():
    return ["end", ""]


def hsrp_lines(sub, role):
    vlan = sub["vlan"]
    prio = 110 if sub["active"] == role else 100
    vip = nth(sub["v4"], 1)
    L = [" standby version 2",
         f" standby {vlan} ip {vip}",
         f" standby {vlan} priority {prio}",
         f" standby {vlan} preempt delay minimum 10",
         f" standby {vlan} timers 1 3",
         f" standby {vlan} name HSRP-V{vlan}"]
    if sub.get("v6"):
        g = 1000 + vlan
        L += [f" standby {g} ipv6 FE80::1",
              f" standby {g} priority {prio}",
              f" standby {g} preempt delay minimum 10",
              f" standby {g} timers 1 3"]
    return L


def gateway_if_body(site, sub, role, ospf):
    """Common L3 gateway body (SVI on HCM cores, sub-interface on branch edges)."""
    L = [f" ip address {gw_addr(sub['v4'], role)} {mask(sub['v4'])}"]
    if sub.get("dhcp"):
        L.append(f" ip helper-address {DHCP_DNS_SERVER}")
    if sub.get("acl_in"):
        L.append(f" ip access-group {sub['acl_in']} in")
    if sub.get("acl_out"):
        L.append(f" ip access-group {sub['acl_out']} out")
    L.append(" no ip redirects")
    if sub.get("v6"):
        L.append(f" ipv6 address {nth(sub['v6'], 2 if role == 'A' else 3)}/64")
        if sub.get("acl6_in"):
            L.append(f" ipv6 traffic-filter {sub['acl6_in']} in")
        if sub.get("acl6_out"):
            L.append(f" ipv6 traffic-filter {sub['acl6_out']} out")
        L.append(f" ipv6 ospf {ospf} area 0")
    L.append(f" ip ospf {ospf} area 0")
    L += hsrp_lines(sub, role)
    return L


# --------------------------------------------------------------------------
# shared policy blocks
# --------------------------------------------------------------------------

def acl_guest():
    return [
        "ip access-list extended ACL-GUEST-IN",
        " remark GUEST: DHCP + Internet only. No RFC1918 destination, no infrastructure.",
        " permit udp any eq bootpc any eq bootps",
        f" permit udp any eq bootpc host {DHCP_DNS_SERVER} eq bootps",
        " deny   ip any 10.0.0.0 0.255.255.255 log",
        " deny   ip any 172.16.0.0 0.15.255.255 log",
        " deny   ip any 192.168.0.0 0.0.255.255 log",
        " permit ip any any",
        "!",
    ]


def acl_iot():
    srv = site_subnet("HCM", 80)
    s4, w4 = srv["v4"].split("/")[0], wildcard(srv["v4"])
    return [
        "ip access-list extended ACL-IOT-IN",
        " remark IoT: DHCP/DNS/NTP + MQTT to the IoT platform at HQ + cloud IoT hub. Nothing else.",
        " permit udp any eq bootpc any eq bootps",
        f" permit udp any eq bootpc host {DHCP_DNS_SERVER} eq bootps",
        f" permit udp any host {DHCP_DNS_SERVER} eq domain",
        f" permit udp any host {DHCP_DNS_SERVER} eq ntp",
        f" permit tcp any {s4} {w4} eq 1883",
        f" permit tcp any {s4} {w4} eq 8883",
        f" permit icmp any {s4} {w4}",
        f" permit tcp any host {SAAS_A} eq 8883",
        " deny   ip any any log",
        "!",
        "ipv6 access-list ACL6-IOT-IN",
        " permit icmp any any nd-ns",
        " permit icmp any any nd-na",
        " permit icmp any any router-solicitation",
        f" permit ipv6 any {srv['v6']}",
        " deny   ipv6 any any log",
        "!",
    ]


def acl_exec():
    e = site_subnet("HCM", 10)
    srv, mg = site_subnet("HCM", 80), site_subnet("HCM", 99)
    n = lambda s: f"{s['v4'].split('/')[0]} {wildcard(s['v4'])}"
    return [
        "ip access-list extended ACL-EXEC-PROTECT",
        " remark Applied OUT on Vlan10: only servers, management and replies may enter the Executive VLAN",
        f" permit tcp any {n(e)} established",
        f" permit ip {n(srv)} {n(e)}",
        f" permit ip {n(mg)} {n(e)}",
        f" permit icmp any {n(e)} echo-reply",
        f" permit icmp any {n(e)} unreachable",
        f" permit icmp any {n(e)} time-exceeded",
        f" deny   ip 10.0.0.0 0.255.255.255 {n(e)} log",
        " permit ip any any",
        "!",
        "ipv6 access-list ACL6-EXEC-PROTECT",
        f" permit tcp any {e['v6']} established",
        f" permit ipv6 {srv['v6']} {e['v6']}",
        f" permit ipv6 {mg['v6']} {e['v6']}",
        f" permit icmp any {e['v6']} echo-reply",
        f" permit icmp any {e['v6']} unreachable",
        f" permit icmp any {e['v6']} time-exceeded",
        f" permit icmp any {e['v6']} packet-too-big",
        f" deny   ipv6 {ENTERPRISE_V6} {e['v6']} log",
        " permit ipv6 any any",
        "!",
    ]


def qos_block(shape_bps=50_000_000):
    return [
        "! ---------------- QoS: classify & mark at the WAN-edge LAN side ----------------",
        "ip access-list extended ACL-QOS-RTP",
        " remark RTP media (VoIP) -- also matches the IP SLA udp-jitter probes",
        " permit udp 10.0.0.0 0.255.255.255 any range 16384 32767",
        "ip access-list extended ACL-QOS-SIGNALING",
        " permit udp 10.0.0.0 0.255.255.255 any range 5060 5061",
        " permit tcp 10.0.0.0 0.255.255.255 any range 5060 5061",
        "ip access-list extended ACL-QOS-CRITICAL",
        " remark Executive/Finance and site-admin subnets",
        " permit ip 10.10.32.0 0.0.3.255 any",
        " permit ip 10.20.28.0 0.0.1.255 any",
        "!",
        "class-map match-any CM-IN-VOICE",
        " match access-group name ACL-QOS-RTP",
        "class-map match-any CM-IN-SIGNALING",
        " match access-group name ACL-QOS-SIGNALING",
        "class-map match-any CM-IN-CRITICAL",
        " match access-group name ACL-QOS-CRITICAL",
        "!",
        "policy-map PM-LAN-MARK-IN",
        " description Trust boundary: re-mark everything entering the WAN edge",
        " class CM-IN-VOICE",
        "  set dscp ef",
        " class CM-IN-SIGNALING",
        "  set dscp cs3",
        " class CM-IN-CRITICAL",
        "  set dscp af31",
        " class class-default",
        "  set dscp default",
        "!",
        "! ---------------- QoS: queue on the WAN transport (LLQ under a shaper) ----------",
        "class-map match-any CM-WAN-VOICE",
        " match dscp ef",
        "class-map match-any CM-WAN-SIGNALING",
        " match dscp cs3",
        "class-map match-any CM-WAN-CRITICAL",
        " match dscp af31",
        "!",
        "policy-map PM-WAN-QUEUING",
        " class CM-WAN-VOICE",
        "  priority percent 30",
        " class CM-WAN-SIGNALING",
        "  bandwidth percent 5",
        " class CM-WAN-CRITICAL",
        "  bandwidth percent 25",
        " class class-default",
        "  fair-queue",
        "!",
        "policy-map PM-WAN-SHAPE",
        f" description Shape to the {shape_bps // 1_000_000} Mbps contracted WAN rate, then LLQ",
        " class class-default",
        f"  shape average {shape_bps}",
        "  service-policy PM-WAN-QUEUING",
        "!",
    ]


def zbf_block():
    return [
        "! ---------------- Zone-based firewall ----------------",
        "zone security INSIDE",
        " description LAN, site interconnects and overlay tunnels",
        "zone security OUTSIDE",
        " description ISP transport (untrusted)",
        "!",
        "class-map type inspect match-any CM-INSIDE-TO-OUTSIDE",
        " match protocol tcp",
        " match protocol udp",
        " match protocol icmp",
        "policy-map type inspect PM-INSIDE-TO-OUTSIDE",
        " class type inspect CM-INSIDE-TO-OUTSIDE",
        "  inspect",
        " class class-default",
        "  drop log",
        "!",
        "ip access-list extended ACL-OUTSIDE-TO-SELF",
        " remark Control plane allowed from the ISP: IKE/IPsec, GRE, BGP, ICMP",
        " permit udp any any eq isakmp",
        " permit udp any any eq non500-isakmp",
        " permit esp any any",
        " permit gre any any",
        " permit tcp any any eq bgp",
        " permit tcp any eq bgp any",
        " permit icmp any any",
        "class-map type inspect match-any CM-OUTSIDE-TO-SELF",
        " match access-group name ACL-OUTSIDE-TO-SELF",
        "policy-map type inspect PM-OUTSIDE-TO-SELF",
        " class type inspect CM-OUTSIDE-TO-SELF",
        "  pass",
        " class class-default",
        "  drop log",
        "!",
        "zone-pair security ZP-INSIDE-OUTSIDE source INSIDE destination OUTSIDE",
        " service-policy type inspect PM-INSIDE-TO-OUTSIDE",
        "zone-pair security ZP-OUTSIDE-SELF source OUTSIDE destination self",
        " service-policy type inspect PM-OUTSIDE-TO-SELF",
        "!",
    ]


def crypto_block():
    return [
        "! ---------------- IPsec (IKEv2) protecting the GRE overlay ----------------",
        "crypto ikev2 proposal TVI-IKEV2-PROP",
        " encryption aes-cbc-256",
        " integrity sha256",
        " group 14",
        "crypto ikev2 policy TVI-IKEV2-POL",
        " proposal TVI-IKEV2-PROP",
        "crypto ikev2 keyring TVI-KEYRING",
        " peer ANY-SITE",
        "  address 0.0.0.0 0.0.0.0",
        f"  pre-shared-key {IKE_PSK}",
        "crypto ikev2 profile TVI-IKEV2-PROFILE",
        " match identity remote address 0.0.0.0",
        " authentication remote pre-share",
        " authentication local pre-share",
        " keyring local TVI-KEYRING",
        " dpd 10 3 on-demand",
        "!",
        "crypto ipsec transform-set TVI-TS esp-aes 256 esp-sha256-hmac",
        " mode transport",
        "crypto ipsec profile TVI-IPSEC-PROFILE",
        " set transform-set TVI-TS",
        " set ikev2-profile TVI-IKEV2-PROFILE",
        "!",
    ]


# --------------------------------------------------------------------------
# role renderers
# --------------------------------------------------------------------------

def render_edge(dev):
    d = DEVICES[dev]
    site = d["site"]
    S = SITES[site]
    asn, ospf = S["asn"], S["ospf"]
    role = gw_role(site, dev)            # branch edges are also the LAN gateways
    isp = isp_link(dev)
    isp_asn = ISPS[isp["isp"]]["asn"]
    ibgp_peer = [n for n, x in DEVICES.items() if x["site"] == site and x["role"] == "edge" and n != dev][0]
    lo6 = lo0_v6(dev)
    peer_lo, peer_lo6 = DEVICES[ibgp_peer]["lo0"], lo0_v6(ibgp_peer)
    s_net = ip.ip_network(S["v4"])
    hcm = site == "HCM"

    L = ios_common(dev, d)
    L += crypto_block()
    L += zbf_block()
    L += qos_block()
    # ---- interfaces
    L += ["interface Loopback0",
          " description Router-ID / iBGP / management loopback",
          f" ip address {d['lo0']} 255.255.255.255",
          f" ipv6 address {lo6}/128",
          f" ip ospf {ospf} area 0",
          f" ipv6 ospf {ospf} area 0",
          "!"]
    L += mgmt_if(d)
    L += [f"interface {full_if(isp['ce_if'])}",
          f" description WAN transport {d['plane']} -> {isp['isp']} {isp['isp_if']} (demarcation point)",
          f" ip address {isp['ce_ip']} {mask(isp['net'])}",
          " ip nat outside",
          " zone-member security OUTSIDE",
          " no ip redirects",
          " no ip unreachables",
          " no ip proxy-arp",
          " no cdp enable",
          " service-policy output PM-WAN-SHAPE",
          " no shutdown",
          "!"]
    passive_off = []
    for lif, a4, net4, a6, peer, pif in p2p_ends(dev):
        L += [f"interface {full_if(lif)}",
              f" description P2P -> {peer} {pif}",
              f" ip address {a4} {mask(net4)}",
              f" ipv6 address {a6}/64",
              " ip nat inside",
              " zone-member security INSIDE",
              " ip ospf network point-to-point",
              f" ip ospf {ospf} area 0",
              " ipv6 ospf network point-to-point",
              f" ipv6 ospf {ospf} area 0"]
        if peer.endswith(("CORE1", "CORE2")):
            L.append(" service-policy input PM-LAN-MARK-IN")
        L += [" no shutdown", "!"]
        passive_off.append(full_if(lif))
    if not hcm:   # router-on-a-stick LAN with HSRP
        trunk_if = [t for t in trunks_of(dev)][0]
        L += [f"interface {full_if(trunk_if[0])}",
              f" description 802.1Q trunk -> {trunk_if[1]} {trunk_if[2]}",
              " no ip address",
              " no shutdown",
              "!"]
        for sub in SUBNETS[site]:
            L += [f"interface {full_if(trunk_if[0])}.{sub['vlan']}",
                  f" description Gateway VLAN {sub['vlan']} {VLANS[sub['vlan']]}",
                  f" encapsulation dot1Q {sub['vlan']}"]
            L += gateway_if_body(site, sub, role, ospf)
            L += [" ip nat inside",
                  " zone-member security INSIDE",
                  " service-policy input PM-LAN-MARK-IN",
                  "!"]
    for t in tunnels_of(dev):
        dst = isp_link(t["peer"])["ce_ip"]
        L += [f"interface Tunnel{t['num']}",
              f" description Overlay plane {t['plane']} -> {t['peer']} Tunnel{t['num']} (GRE/IPsec)",
              " bandwidth 50000",
              f" ip address {t['ip']} {mask(t['v4'])}",
              " ip mtu 1400",
              " ip tcp adjust-mss 1360",
              f" ipv6 address {t['ip6']}/64",
              " ipv6 mtu 1400",
              " zone-member security INSIDE",
              " qos pre-classify",
              f" tunnel source {full_if(isp['ce_if'])}",
              f" tunnel destination {dst}",
              " tunnel protection ipsec profile TVI-IPSEC-PROFILE",
              "!"]
    # ---- policy objects
    if not hcm:
        if any(s.get("guest") for s in SUBNETS[site]):
            L += acl_guest()
        if any(s.get("acl_in") == "ACL-IOT-IN" for s in SUBNETS[site]):
            L += acl_iot()
    L += ["ip access-list extended ACL-NAT",
          " remark PAT for Internet-bound traffic only; site-to-site traffic is never translated",
          " deny   ip 10.0.0.0 0.255.255.255 10.0.0.0 0.255.255.255",
          f" permit ip {s_net.network_address} {s_net.hostmask} any",
          f"ip nat inside source list ACL-NAT interface {full_if(isp['ce_if'])} overload",
          "!"]
    L += [f"ip route {s_net.network_address} {s_net.netmask} Null0 254 name SITE-AGGREGATE",
          f"ipv6 route {S['v6']} Null0 254",
          "!",
          "ip prefix-list PL-DEFAULT-ONLY seq 5 permit 0.0.0.0/0",
          "ip prefix-list PL-DENY-ALL seq 5 deny 0.0.0.0/0 le 32",
          "ip prefix-list PL-ENTERPRISE-IN seq 5 permit 10.0.0.0/8 ge 16 le 24",
          f"ip prefix-list PL-SITE-OUT seq 5 permit {S['v4']}",
          f"ipv6 prefix-list PL6-ENTERPRISE-IN seq 5 permit {ENTERPRISE_V6} ge 48 le 48",
          f"ipv6 prefix-list PL6-SITE-OUT seq 5 permit {S['v6']}",
          "!"]
    if hcm:
        L += [f"ip prefix-list PL-OTHER-SITES seq 5 deny {S['v4']} le 32",
              "ip prefix-list PL-OTHER-SITES seq 10 permit 10.0.0.0/8 ge 16 le 24",
              f"ipv6 prefix-list PL6-OTHER-SITES seq 5 deny {S['v6']} le 128",
              f"ipv6 prefix-list PL6-OTHER-SITES seq 10 permit {ENTERPRISE_V6} ge 48 le 48",
              "!",
              "route-map RM-BGP-TO-OSPF permit 10",
              " description Inject remote-site aggregates into the HQ underlay",
              " match ip address prefix-list PL-OTHER-SITES",
              "route-map RM6-BGP-TO-OSPF permit 10",
              " match ipv6 address prefix-list PL6-OTHER-SITES",
              "!"]
    # ---- OSPF underlay
    L += [f"router ospf {ospf}",
          f" router-id {d['lo0']}",
          " auto-cost reference-bandwidth 100000",
          " passive-interface default"]
    L += [f" no passive-interface {i}" for i in passive_off]
    if hcm:
        L += [" default-information originate",
              f" redistribute bgp {asn} subnets route-map RM-BGP-TO-OSPF"]
    L += ["!", f"ipv6 router ospf {ospf}",
          f" router-id {d['lo0']}",
          " auto-cost reference-bandwidth 100000",
          " passive-interface default"]
    L += [f" no passive-interface {i}" for i in passive_off]
    if hcm:
        L += [f" redistribute bgp {asn} route-map RM6-BGP-TO-OSPF"]
    L += ["!"]
    # ---- BGP overlay
    tl = list(tunnels_of(dev))
    L += [f"router bgp {asn}",
          f" bgp router-id {d['lo0']}",
          " bgp log-neighbor-changes",
          " no bgp default ipv4-unicast",
          f" neighbor {isp['isp_ip']} remote-as {isp_asn}",
          f" neighbor {isp['isp_ip']} description eBGP {isp['isp']} (Internet transport {d['plane']})",
          f" neighbor {peer_lo} remote-as {asn}",
          f" neighbor {peer_lo} description iBGP {ibgp_peer}",
          f" neighbor {peer_lo} update-source Loopback0",
          f" neighbor {peer_lo6} remote-as {asn}",
          f" neighbor {peer_lo6} description iBGP-v6 {ibgp_peer}",
          f" neighbor {peer_lo6} update-source Loopback0"]
    for t in tl:
        pasn = SITES[DEVICES[t['peer']]['site']]['asn']
        L += [f" neighbor {t['peer_ip']} remote-as {pasn}",
              f" neighbor {t['peer_ip']} description eBGP overlay {t['peer']} via Tunnel{t['num']}",
              f" neighbor {t['peer_ip']} timers 5 15",
              f" neighbor {t['peer_ip6']} remote-as {pasn}",
              f" neighbor {t['peer_ip6']} description eBGP-v6 overlay {t['peer']} via Tunnel{t['num']}",
              f" neighbor {t['peer_ip6']} timers 5 15"]
    L += [" !", " address-family ipv4",
          f"  network {s_net.network_address} mask {s_net.netmask}",
          f"  neighbor {isp['isp_ip']} activate",
          f"  neighbor {isp['isp_ip']} prefix-list PL-DEFAULT-ONLY in",
          f"  neighbor {isp['isp_ip']} prefix-list PL-DENY-ALL out",
          f"  neighbor {peer_lo} activate",
          f"  neighbor {peer_lo} next-hop-self"]
    for t in tl:
        L += [f"  neighbor {t['peer_ip']} activate",
              f"  neighbor {t['peer_ip']} prefix-list PL-ENTERPRISE-IN in",
              f"  neighbor {t['peer_ip']} prefix-list PL-SITE-OUT out"]
    L += [" exit-address-family", " !", " address-family ipv6",
          f"  network {S['v6']}",
          f"  neighbor {peer_lo6} activate",
          f"  neighbor {peer_lo6} next-hop-self"]
    for t in tl:
        L += [f"  neighbor {t['peer_ip6']} activate",
              f"  neighbor {t['peer_ip6']} prefix-list PL6-ENTERPRISE-IN in",
              f"  neighbor {t['peer_ip6']} prefix-list PL6-SITE-OUT out"]
    L += [" exit-address-family", "!",
          "ip sla responder",
          "!"]
    L += vty_block()
    L += end()
    return L


def render_core(dev):
    d = DEVICES[dev]
    site = d["site"]
    ospf = SITES[site]["ospf"]
    role = gw_role(site, dev)
    vl = site_vlans(site)
    mine = [s["vlan"] for s in SUBNETS[site] if s["active"] == role]
    other = [v for v in vl if v not in mine]
    if role == "A":
        mine = mine + [HCM_CORE_TRANSIT_VLAN]
    else:
        other = other + [HCM_CORE_TRANSIT_VLAN]
    L = ios_common(dev, d)
    L += ["ip routing", "!", "vtp mode transparent", "!",
          "spanning-tree mode rapid-pvst",
          "spanning-tree extend system-id",
          "spanning-tree loopguard default",
          f"spanning-tree vlan {','.join(map(str, mine))} priority 24576",
          f"spanning-tree vlan {','.join(map(str, other))} priority 28672",
          "!"]
    for v in vl + [HCM_CORE_TRANSIT_VLAN, 999]:
        L += [f"vlan {v}", f" name {VLANS[v]}"]
    L += ["!"]
    po_allowed = ",".join(map(str, vl + [HCM_CORE_TRANSIT_VLAN]))
    acc_allowed = ",".join(map(str, vl))
    L += ["interface Port-channel1",
          f" description LACP L2 trunk -> {[n for n in GATEWAYS[site] if n != dev][0]} Po1",
          " switchport trunk encapsulation dot1q",
          " switchport mode trunk",
          " switchport trunk native vlan 999",
          f" switchport trunk allowed vlan {po_allowed}",
          " switchport nonegotiate",
          "!"]
    used = {"Gi0/0"}
    for lif, peer, pif, po in trunks_of(dev):
        used.add(lif)
        L += [f"interface {full_if(lif)}",
              f" description {'Po1 member' if po else 'L2 trunk'} -> {peer} {pif}",
              " switchport trunk encapsulation dot1q",
              " switchport mode trunk",
              " switchport trunk native vlan 999",
              f" switchport trunk allowed vlan {po_allowed if po else acc_allowed}",
              " switchport nonegotiate"]
        if po:
            L += [f" channel-group {po} mode active"]
        else:
            L += [" spanning-tree guard root"]
        L += [" no shutdown", "!"]
    L += mgmt_if(d, l2=True)
    passive_off = []
    for lif, a4, net4, a6, peer, pif in p2p_ends(dev):
        if lif.startswith("Vlan"):
            L += [f"interface {lif}", f" description OSPF transit -> {peer} (over Po1)"]
        else:
            used.add(lif)
            L += [f"interface {full_if(lif)}", f" description L3 uplink -> {peer} {pif}", " no switchport"]
        L += [f" ip address {a4} {mask(net4)}",
              f" ipv6 address {a6}/64",
              " ip ospf network point-to-point",
              f" ip ospf {ospf} area 0",
              " ipv6 ospf network point-to-point",
              f" ipv6 ospf {ospf} area 0",
              " no shutdown", "!"]
        passive_off.append(full_if(lif))
    L += ["interface Loopback0",
          f" ip address {d['lo0']} 255.255.255.255",
          f" ipv6 address {lo0_v6(dev)}/128",
          f" ip ospf {ospf} area 0",
          f" ipv6 ospf {ospf} area 0",
          "!"]
    for sub in SUBNETS[site]:
        L += [f"interface Vlan{sub['vlan']}",
              f" description Gateway {VLANS[sub['vlan']]} ({'HSRP active' if sub['active'] == role else 'HSRP standby'})"]
        L += gateway_if_body(site, sub, role, ospf)
        L += [" no shutdown", "!"]
    # unused ports
    for g in range(4):
        for p in range(4):
            n = f"Gi{g}/{p}"
            if n not in used:
                L += [f"interface {full_if(n)}", " description UNUSED", " switchport mode access",
                      " switchport access vlan 999", " shutdown", "!"]
    L += acl_exec() + acl_guest()
    L += [f"router ospf {ospf}", f" router-id {d['lo0']}", " auto-cost reference-bandwidth 100000",
          " passive-interface default"] + [f" no passive-interface {i}" for i in passive_off] + ["!"]
    L += [f"ipv6 router ospf {ospf}", f" router-id {d['lo0']}", " auto-cost reference-bandwidth 100000",
          " passive-interface default"] + [f" no passive-interface {i}" for i in passive_off] + ["!"]
    L += vty_block() + end()
    return L


def render_access(dev):
    d = DEVICES[dev]
    site = d["site"]
    vl = site_vlans(site)
    snoop = [s["vlan"] for s in SUBNETS[site] if s.get("snoop")]
    gw99 = nth(site_subnet(site, 99)["v4"], 1)
    L = ios_common(dev, d, routing=False, v6=False)
    L += ["no ip routing", f"ip default-gateway {gw99}", "!", "vtp mode transparent", "!",
          "spanning-tree mode rapid-pvst",
          "spanning-tree extend system-id"]
    if site != "HCM":   # branch: the access switch is the only bridge -> make it root explicitly
        L += [f"spanning-tree vlan {','.join(map(str, vl))} priority 24576"]
    L += ["!"]
    for v in vl + [999]:
        L += [f"vlan {v}", f" name {VLANS[v]}"]
    L += ["!",
          f"ip dhcp snooping vlan {','.join(map(str, snoop))}",
          "no ip dhcp snooping information option",
          "ip dhcp snooping",
          f"ip arp inspection vlan {','.join(map(str, snoop))}",
          "ip arp inspection validate src-mac dst-mac",
          "ip arp inspection log-buffer entries 64",
          "errdisable recovery cause bpduguard",
          "errdisable recovery cause psecure-violation",
          "errdisable recovery interval 120",
          "!"]
    used = {"Gi0/0"}
    allowed = ",".join(map(str, vl))
    for lif, peer, pif, po in trunks_of(dev):
        used.add(lif)
        L += [f"interface {full_if(lif)}",
              f" description Uplink trunk -> {peer} {pif}",
              " switchport trunk encapsulation dot1q",
              " switchport mode trunk",
              " switchport trunk native vlan 999",
              f" switchport trunk allowed vlan {allowed}",
              " switchport nonegotiate",
              " ip dhcp snooping trust",
              " ip arp inspection trust",
              " no shutdown", "!"]
    for sw, pif, ep, epif, data, voice in ACCESS_PORTS:
        if sw != dev:
            continue
        used.add(pif)
        L += [f"interface {full_if(pif)}",
              f" description Access -> {ep} {epif} (VLAN {data} {VLANS[data]})",
              " switchport mode access",
              f" switchport access vlan {data}"]
        if voice:
            L += [f" switchport voice vlan {voice}"]
        L += [" switchport nonegotiate",
              f" switchport port-security maximum {3 if voice else 2}",
              " switchport port-security violation restrict",
              " switchport port-security mac-address sticky",
              " switchport port-security",
              " spanning-tree portfast",
              " spanning-tree bpduguard enable"]
        if data in snoop:
            L += [" ip dhcp snooping limit rate 15"]
        L += [" no shutdown", "!"]
    L += mgmt_if(d, l2=True)
    L += ["interface Vlan99", " description In-band management",
          f" ip address {d['svi99']} {mask(site_subnet(site, 99)['v4'])}", " no shutdown", "!",
          "interface Vlan1", " no ip address", " shutdown", "!"]
    for g in range(4):
        for p in range(4):
            n = f"Gi{g}/{p}"
            if n not in used:
                L += [f"interface {full_if(n)}", " description UNUSED", " switchport mode access",
                      " switchport access vlan 999", " spanning-tree bpduguard enable", " shutdown", "!"]
    L += vty_block() + end()
    return L


def render_server(dev):
    d = DEVICES[dev]
    srv = site_subnet("HCM", 80)
    L = ios_common(dev, d, dns_lookup=True)
    L += ["interface GigabitEthernet0/1",
          " description Campus services NIC -> HCM-ACC1 Gi2/0 (VLAN 80)",
          f" ip address {d['ip']} {mask(srv['v4'])}",
          f" ipv6 address {nth(srv['v6'], 0x10)}/64",
          " no shutdown", "!"]
    L += mgmt_if(d)
    L += [f"ip route 0.0.0.0 0.0.0.0 {nth(srv['v4'], 1)} name HSRP-VIP",
          "ipv6 route ::/0 GigabitEthernet0/1 FE80::1",
          "!",
          "! ---------------- Centralised DHCP for all three sites ----------------"]
    for site in SITES:
        for sub in SUBNETS[site]:
            if sub.get("dhcp"):
                net = sub["v4"]
                L.append(f"ip dhcp excluded-address {nth(net, 1)} {nth(net, 20)}")
    L.append("!")
    for site in SITES:
        for sub in SUBNETS[site]:
            if not sub.get("dhcp"):
                continue
            net = ip.ip_network(sub["v4"])
            L += [f"ip dhcp pool {site}-V{sub['vlan']}-{VLANS[sub['vlan']]}",
                  f" network {net.network_address} {net.netmask}",
                  f" default-router {nth(sub['v4'], 1)}"]
            if sub.get("guest"):
                L += [f" dns-server {PUBLIC_DNS}", " lease 0 4"]
            else:
                L += [f" dns-server {DHCP_DNS_SERVER}", f" domain-name {DOMAIN}", " lease 1"]
            if sub.get("wlc"):
                o = WLC_IP.split(".")
                hexip = "".join(f"{int(x):02x}" for x in o)
                L += [f" option 43 hex f104.{hexip[:4]}.{hexip[4:]}"]
            L.append("!")
    L += ["! ---------------- Internal DNS (forwards unknown names to the Internet resolver) -----",
          "ip dns server",
          f"ip name-server {PUBLIC_DNS}"]
    for n, x in DEVICES.items():
        if x["lab"] == "A" and x.get("lo0") and x["role"] != "isp":
            L.append(f"ip host {n.lower()}.{DOMAIN} {x['lo0']}")
        elif x.get("svi99"):
            L.append(f"ip host {n.lower()}.{DOMAIN} {x['svi99']}")
    L += [f"ip host hcm-srv1.{DOMAIN} {d['ip']}", f"ip host wlc.{DOMAIN} {WLC_IP}", "!",
          "! ---------------- NTP master for the enterprise ----------------",
          "ntp master 4", "!",
          "! ---------------- Simulated VoIP (G.711) towards each branch ----------------",
          "ip sla 10",
          f" udp-jitter {DEVICES['HAN-EDG1']['lo0']} 16384 source-ip {d['ip']} codec g711ulaw",
          "  tos 184",
          "  tag VOIP-HCM-TO-HAN",
          "  frequency 30",
          "ip sla schedule 10 life forever start-time now",
          "ip sla 20",
          f" udp-jitter {DEVICES['DAD-EDG1']['lo0']} 16386 source-ip {d['ip']} codec g711ulaw",
          "  tos 184",
          "  tag VOIP-HCM-TO-DAD",
          "  frequency 30",
          "ip sla schedule 20 life forever start-time now",
          "!"]
    L += vty_block() + end()
    return L


def render_isp(dev):
    d = DEVICES[dev]
    I = ISPS[dev]
    blk = ip.ip_network(I["block"])
    L = ios_common(dev, d, v6=False)
    L += ["interface Loopback0", f" ip address {I['lo0']} 255.255.255.255", "!"]
    if dev == "ISP-A":
        L += ["interface Loopback1", " description Public SaaS / cloud application",
              f" ip address {SAAS_A} 255.255.255.255", "!",
              "interface Loopback2", " description Public DNS resolver",
              f" ip address {PUBLIC_DNS} 255.255.255.255", "!"]
    else:
        L += ["interface Loopback1", " description Public cloud target B",
              f" ip address {SAAS_B} 255.255.255.255", "!"]
    L += mgmt_if(d)
    nbrs = []
    for isp, iif, ce, cif, net in ISP_LINKS:
        if isp != dev:
            continue
        L += [f"interface {full_if(iif)}", f" description Customer TVI {ce} {cif}",
              f" ip address {nth(net, 1)} {mask(net)}", " no shutdown", "!"]
        nbrs.append((nth(net, 2), SITES[DEVICES[ce]['site']]['asn'], ce))
    a, aif, b, bif, net = ISP_PEERING
    me_if, me_ip = (aif, nth(net, 1)) if dev == a else (bif, nth(net, 2))
    peer, peer_ip = (b, nth(net, 2)) if dev == a else (a, nth(net, 1))
    L += [f"interface {full_if(me_if)}", f" description Peering -> {peer}",
          f" ip address {me_ip} {mask(net)}", " no shutdown", "!"]
    L += [f"ip route {blk.network_address} {blk.netmask} Null0"]
    if dev == "ISP-A":
        L += ["ip route 192.0.2.0 255.255.255.0 Null0"]
    L += ["!", "ip prefix-list PL-DEFAULT-ONLY seq 5 permit 0.0.0.0/0",
          "ip prefix-list PL-DENY-ALL seq 5 deny 0.0.0.0/0 le 32", "!",
          f"router bgp {I['asn']}", f" bgp router-id {I['lo0']}", " bgp log-neighbor-changes",
          " no bgp default ipv4-unicast"]
    for nip, asn, ce in nbrs:
        L += [f" neighbor {nip} remote-as {asn}", f" neighbor {nip} description Customer TVI {ce}"]
    L += [f" neighbor {peer_ip} remote-as {ISPS[peer]['asn']}", f" neighbor {peer_ip} description Peering {peer}",
          " !", " address-family ipv4",
          f"  network {blk.network_address} mask {blk.netmask}"]
    if dev == "ISP-A":
        L += ["  network 192.0.2.0 mask 255.255.255.0"]
    else:
        L += [f"  network {SAAS_B} mask 255.255.255.255"]
    for nip, asn, ce in nbrs:
        L += [f"  neighbor {nip} activate", f"  neighbor {nip} default-originate",
              f"  neighbor {nip} prefix-list PL-DENY-ALL in", f"  neighbor {nip} prefix-list PL-DEFAULT-ONLY out"]
    L += [f"  neighbor {peer_ip} activate", " exit-address-family", "!"]
    if dev == "ISP-A":
        L += ["ip dns server",
              f"ip host saas.cloud.example {SAAS_A}",
              f"ip host www.example.com {SAAS_A}",
              f"ip host cloud-b.example {SAAS_B}", "!"]
    L += vty_block() + end()
    return L


def render_veos(dev):
    d = DEVICES[dev]
    DCc = DC
    L = ["! " + "=" * 72, f"! TVI Innovations -- {dev} (Arista vEOS, {d['role']}) -- Lab B EVPN-VXLAN fabric",
         "! Generated by tools/build_configs.py. After pasting: 'write' then 'reload' once",
         "! (the multi-agent routing model is required for EVPN).", "! " + "=" * 72,
         f"hostname {dev}",
         "service routing protocols model multi-agent",
         "!",
         f"username {LAB_USER} privilege 15 role network-admin secret {LAB_PASSWORD}",
         f"ip domain-name {DOMAIN}",
         "clock timezone Asia/Ho_Chi_Minh",
         "!",
         "management ssh", "   idle-timeout 15", "!",
         "interface Management1", f"   ip address {d['mgmt']}/24", "!"]
    if d["role"] == "leaf":
        for v in DCc["vlans"]:
            L += [f"vlan {v['vlan']}", f"   name {v['name']}"]
        L += ["!", f"vrf instance {DCc['vrf']}", "!",
              f"ip virtual-router mac-address {DCc['anycast_mac']}", "!"]
    L += ["ip routing"]
    if d["role"] == "leaf":
        L += [f"ip routing vrf {DCc['vrf']}"]
    L += ["!"]
    for s, sif, lf, lif, net in DCc["fabric_links"]:
        if dev == s:
            me, peer, pif, a = sif, lf, lif, nth(net, 0)
        elif dev == lf:
            me, peer, pif, a = lif, s, sif, nth(net, 1)
        else:
            continue
        L += [f"interface {me}", f"   description Fabric -> {peer} {pif}", "   no switchport", "   mtu 9214",
              f"   ip address {a}/31", "   ip ospf network point-to-point", "!"]
    L += ["interface Loopback0", "   description Router-ID / BGP EVPN peering", f"   ip address {d['lo0']}/32", "!"]
    if d["role"] == "leaf":
        L += ["interface Loopback1", "   description VXLAN VTEP source", f"   ip address {d['vtep']}/32", "!"]
        for lf, lif, h, vlan, hip in DCc["hosts"]:
            if lf == dev:
                L += [f"interface {lif}", f"   description Host {h} ({hip})", "   switchport access vlan " + str(vlan),
                      "   spanning-tree portfast", "!"]
        for v in DCc["vlans"]:
            L += [f"interface Vlan{v['vlan']}", f"   description Anycast gateway {v['name']}",
                  f"   vrf {DCc['vrf']}", f"   ip address virtual {nth(v['v4'], 1)}/24", "!"]
        L += ["interface Vxlan1", "   vxlan source-interface Loopback1", "   vxlan udp-port 4789"]
        for v in DCc["vlans"]:
            L += [f"   vxlan vlan {v['vlan']} vni {v['vni']}"]
        L += [f"   vxlan vrf {DCc['vrf']} vni {DCc['l3vni']}", "!"]
    L += ["router ospf 1", f"   router-id {d['lo0']}", "   passive-interface Loopback0"]
    if d["role"] == "leaf":
        L += ["   passive-interface Loopback1"]
    L += ["   network 10.10.190.0/24 area 0.0.0.0", "   network 10.10.191.0/24 area 0.0.0.0",
          "   max-lsa 12000", "!"]
    spines = [n for n, x in DEVICES.items() if x.get("role") == "spine"]
    leaves = [n for n, x in DEVICES.items() if x.get("role") == "leaf"]
    L += [f"router bgp {DCc['asn']}", f"   router-id {d['lo0']}", "   no bgp default ipv4-unicast",
          "   maximum-paths 4 ecmp 4"]
    if d["role"] == "spine":
        L += ["   neighbor LEAVES peer group", f"   neighbor LEAVES remote-as {DCc['asn']}",
              "   neighbor LEAVES update-source Loopback0", "   neighbor LEAVES route-reflector-client",
              "   neighbor LEAVES send-community extended"]
        L += [f"   neighbor {DEVICES[x]['lo0']} peer group LEAVES" for x in leaves]
        L += ["   !", "   address-family evpn", "      neighbor LEAVES activate", "!"]
    else:
        L += ["   neighbor SPINES peer group", f"   neighbor SPINES remote-as {DCc['asn']}",
              "   neighbor SPINES update-source Loopback0", "   neighbor SPINES send-community extended"]
        L += [f"   neighbor {DEVICES[x]['lo0']} peer group SPINES" for x in spines]
        for v in DCc["vlans"]:
            L += ["   !", f"   vlan {v['vlan']}", f"      rd {d['lo0']}:{v['vni']}",
                  f"      route-target both {v['vlan']}:{v['vni']}", "      redistribute learned"]
        L += ["   !", "   address-family evpn", "      neighbor SPINES activate",
              "   !", f"   vrf {DCc['vrf']}", f"      rd {d['lo0']}:{DCc['l3vni']}",
              f"      route-target import evpn {DCc['l3vni']}:{DCc['l3vni']}",
              f"      route-target export evpn {DCc['l3vni']}:{DCc['l3vni']}",
              "      redistribute connected", "!"]
    L += ["end", ""]
    return L


def render_vpcs():
    """VPCS start-up snippets (DHCP for v4, SLAAC for v6)."""
    out = {}
    for sw, pif, ep, epif, data, voice in ACCESS_PORTS:
        if not ep.startswith("PC-"):
            continue
        site = DEVICES[sw]["site"]
        sub = site_subnet(site, data)
        L = [f"# {ep} -- VLAN {data} {VLANS[data]} on {sw} {pif}", f"set pcname {ep}", "ip dhcp"]
        if sub.get("v6"):
            L.append("ip auto")
        L.append("save")
        out[ep] = L
    for lf, lif, h, vlan, hip in DC["hosts"]:
        v = [x for x in DC["vlans"] if x["vlan"] == vlan][0]
        out[h] = [f"# {h} -- Lab B host on {lf} {lif} (VLAN {vlan})", f"set pcname {h}",
                  f"ip {hip}/24 {nth(v['v4'], 1)}", "save"]
    return out


RENDER = {"edge": render_edge, "core": render_core, "access": render_access,
          "server": render_server, "isp": render_isp, "spine": render_veos, "leaf": render_veos}


def build(outdir=None):
    outdir = outdir or os.path.join(ROOT, "configs")
    written = []
    for dev, d in DEVICES.items():
        lab = "labA" if d["lab"] == "A" else "labB"
        os.makedirs(os.path.join(outdir, lab), exist_ok=True)
        text = "\n".join(RENDER[d["role"]](dev))
        p = os.path.join(outdir, lab, f"{dev}.cfg")
        with open(p, "w") as f:
            f.write(text)
        written.append(p)
    vp = render_vpcs()
    os.makedirs(os.path.join(outdir, "vpcs"), exist_ok=True)
    for name, L in vp.items():
        with open(os.path.join(outdir, "vpcs", f"{name}.vpc"), "w") as f:
            f.write("\n".join(L) + "\n")
    return written


if __name__ == "__main__":
    for p in build():
        print("wrote", os.path.relpath(p, ROOT))
