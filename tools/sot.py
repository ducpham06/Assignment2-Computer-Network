"""
TVI Network -- Source of Truth (SoT)
====================================
Every address, VLAN, link, tunnel and AS number used anywhere in the project
(configs, IP plan, diagrams, report tables, automation inventory) is defined
here exactly once. Other tools import this module and render from it, so the
documentation can never drift away from the device configurations.
"""
import ipaddress as ip

DOMAIN = "tvi.lab"
MGMT_NET = "172.16.99.0/24"          # out-of-band management (EVE-NG Cloud0)
NMS_HOST = "172.16.99.1"             # automation / syslog station
DHCP_DNS_SERVER = "10.10.43.10"      # HCM-SRV1 (centralised DHCP, DNS, NTP)
WLC_IP = "10.10.43.20"               # design-only virtual WLC (CAPWAP)
PUBLIC_DNS = "192.0.2.53"            # resolver hosted on ISP-A ("Internet")
SAAS_A = "192.0.2.10"                # "SaaS / cloud" target on ISP-A
SAAS_B = "198.51.100.200"            # second Internet target on ISP-B
ENTERPRISE_V4 = "10.0.0.0/8"
ENTERPRISE_V6 = "2001:db8:a000::/40"
WAN_OVERLAY_V4 = "10.0.0.0/24"
WAN_OVERLAY_V6 = "2001:db8:a000::/48"

# --------------------------------------------------------------------------
# Sites
# --------------------------------------------------------------------------
SITES = {
    "HCM": dict(name="Ho Chi Minh City HQ", city="Ho Chi Minh City",
                v4="10.10.0.0/16", v6="2001:db8:a010::/48", asn=65010, ospf=10,
                users_now=2000, users_2030=5000),
    "HAN": dict(name="Hanoi R&D Campus", city="Hanoi",
                v4="10.20.0.0/16", v6="2001:db8:a020::/48", asn=65020, ospf=20,
                users_now=1500, users_2030=3500),
    "DAD": dict(name="Da Nang Logistics Hub", city="Da Nang",
                v4="10.30.0.0/16", v6="2001:db8:a030::/48", asn=65030, ospf=30,
                users_now=500, users_2030=1500),
}

ISPS = {
    "ISP-A": dict(asn=65100, block="203.0.113.0/24", lo0="203.0.113.254",
                  desc="Broadband Internet transport (transport A)"),
    "ISP-B": dict(asn=65200, block="198.51.100.0/24", lo0="198.51.100.254",
                  desc="Second carrier, emulates MPLS/business-fibre underlay (transport B)"),
}
ISP_PEERING = ("ISP-A", "Gi0/4", "ISP-B", "Gi0/4", "203.0.113.248/30")

# --------------------------------------------------------------------------
# VLAN catalogue (enterprise-wide IDs, re-used at every site)
# --------------------------------------------------------------------------
VLANS = {
    10: "EXEC_FINANCE",
    12: "CORP_STAFF",
    20: "RND_ENGINEERING",
    30: "LOGISTICS_OPS",
    40: "VOICE",
    50: "IOT_DEVICES",
    60: "GUEST",
    70: "WLAN_AP",
    80: "SERVERS",
    99: "MANAGEMENT",
    900: "CORE_TRANSIT",
    999: "NATIVE_UNUSED",
}

# --------------------------------------------------------------------------
# Address pools (design, sized for 2030) -- VLSM, largest first per site.
# Every pool is carved into /24 access blocks (<=254 hosts per broadcast
# domain); the lab deploys the first block of each pool.
# --------------------------------------------------------------------------
POOLS = [
    # site, vlan/purpose, prefix, need_2030, note
    ("HCM", 12, "10.10.0.0/20",  4000, "Corporate staff, 16 x /24 access blocks"),
    ("HCM", 40, "10.10.16.0/20", 3500, "IP phones / softphones"),
    ("HCM", 10, "10.10.32.0/22", 600,  "Executives & Finance"),
    ("HCM", 60, "10.10.36.0/22", 1000, "Guest Wi-Fi (Internet only)"),
    ("HCM", 20, "10.10.40.0/23", 400,  "Engineers based at HQ"),
    ("HCM", 70, "10.10.42.0/24", 200,  "Access points (CAPWAP to WLC)"),
    ("HCM", 80, "10.10.43.0/24", 120,  "Campus services (DHCP/DNS/NTP/WLC)"),
    ("HCM", 99, "10.10.44.0/24", 150,  "In-band device management"),
    ("HCM", 50, "10.10.48.0/20", 2000, "HQ IoT (cameras, badge readers, BMS)"),
    ("HCM", "DC", "10.10.128.0/18", None, "Data-centre EVPN-VXLAN fabric (tenants, underlay, VTEPs)"),
    ("HCM", "INFRA", "10.10.254.0/24", None, "Point-to-point links (/30)"),
    ("HCM", "LOOP", "10.10.255.0/24", None, "Router/switch loopbacks (/32)"),
    ("HAN", 20, "10.20.0.0/20",  3500, "R&D engineers, 16 x /24 access blocks"),
    ("HAN", 40, "10.20.16.0/21", 2000, "IP phones"),
    ("HAN", 60, "10.20.24.0/22", 600,  "Guest Wi-Fi"),
    ("HAN", 10, "10.20.28.0/23", 300,  "Site management & admin"),
    ("HAN", 70, "10.20.30.0/24", 150,  "Access points"),
    ("HAN", 99, "10.20.31.0/24", 100,  "In-band device management"),
    ("HAN", 50, "10.20.32.0/20", 1500, "Lab IoT / sensors"),
    ("HAN", "AI", "10.20.64.0/18", None, "AI-lab GPU cluster / private cloud fabric"),
    ("HAN", "INFRA", "10.20.254.0/24", None, "Point-to-point links"),
    ("HAN", "LOOP", "10.20.255.0/24", None, "Loopbacks"),
    ("DAD", 50, "10.30.0.0/17",  25000, "Warehouse IoT: scanners, AGVs, trackers (128 x /24 zones)"),
    ("DAD", 30, "10.30.128.0/21", 1200, "Logistics operations staff"),
    ("DAD", 40, "10.30.136.0/22", 800,  "IP phones"),
    ("DAD", 60, "10.30.140.0/23", 300,  "Guest / driver Wi-Fi"),
    ("DAD", 70, "10.30.142.0/23", 400,  "Wi-Fi 6/7 access points (dense warehouse)"),
    ("DAD", 99, "10.30.144.0/24", 100,  "In-band device management"),
    ("DAD", "INFRA", "10.30.254.0/24", None, "Point-to-point links"),
    ("DAD", "LOOP", "10.30.255.0/24", None, "Loopbacks"),
    ("WAN", "OVERLAY", "10.0.0.0/24", None, "IPsec/GRE overlay tunnels (/30)"),
    ("WAN", "ZTNA", "10.0.64.0/18", None, "SASE/ZTNA remote-user pool (design)"),
]

# --------------------------------------------------------------------------
# Deployed gateway subnets (Lab A). v6 /64 = <site /48>:<VLAN><block>::/64
# active: which gateway of the pair is HSRP active (A = first, B = second)
# --------------------------------------------------------------------------
GATEWAYS = {
    "HCM": ("HCM-CORE1", "HCM-CORE2"),
    "HAN": ("HAN-EDG1", "HAN-EDG2"),
    "DAD": ("DAD-EDG1", "DAD-EDG2"),
}
SUBNETS = {
    "HCM": [
        dict(vlan=10, v4="10.10.32.0/24", v6="2001:db8:a010:1001::/64", active="A", dhcp=True,
             acl_out="ACL-EXEC-PROTECT", acl6_out="ACL6-EXEC-PROTECT", snoop=True),
        dict(vlan=12, v4="10.10.0.0/24",  v6="2001:db8:a010:1201::/64", active="A", dhcp=True, snoop=True),
        dict(vlan=40, v4="10.10.16.0/24", v6="2001:db8:a010:4001::/64", active="A", dhcp=True, snoop=True),
        dict(vlan=60, v4="10.10.36.0/24", v6=None, active="B", dhcp=True, acl_in="ACL-GUEST-IN", snoop=True, guest=True),
        dict(vlan=70, v4="10.10.42.0/24", v6="2001:db8:a010:7001::/64", active="B", dhcp=True, wlc=True),
        dict(vlan=80, v4="10.10.43.0/24", v6="2001:db8:a010:8001::/64", active="A", dhcp=False),
        dict(vlan=99, v4="10.10.44.0/24", v6="2001:db8:a010:9901::/64", active="B", dhcp=False),
    ],
    "HAN": [
        dict(vlan=20, v4="10.20.0.0/24",  v6="2001:db8:a020:2001::/64", active="A", dhcp=True, snoop=True),
        dict(vlan=40, v4="10.20.16.0/24", v6="2001:db8:a020:4001::/64", active="B", dhcp=True, snoop=True),
        dict(vlan=60, v4="10.20.24.0/24", v6=None, active="B", dhcp=True, acl_in="ACL-GUEST-IN", snoop=True, guest=True),
        dict(vlan=99, v4="10.20.31.0/24", v6="2001:db8:a020:9901::/64", active="A", dhcp=False),
    ],
    "DAD": [
        dict(vlan=30, v4="10.30.128.0/24", v6="2001:db8:a030:3001::/64", active="A", dhcp=True, snoop=True),
        dict(vlan=40, v4="10.30.136.0/24", v6="2001:db8:a030:4001::/64", active="B", dhcp=True, snoop=True),
        dict(vlan=50, v4="10.30.0.0/24",   v6="2001:db8:a030:5001::/64", active="B", dhcp=True,
             acl_in="ACL-IOT-IN", acl6_in="ACL6-IOT-IN", snoop=True),
        dict(vlan=60, v4="10.30.140.0/24", v6=None, active="B", dhcp=True, acl_in="ACL-GUEST-IN", snoop=True, guest=True),
        dict(vlan=99, v4="10.30.144.0/24", v6="2001:db8:a030:9901::/64", active="A", dhcp=False),
    ],
}
HCM_CORE_TRANSIT_VLAN = 900

# --------------------------------------------------------------------------
# Devices (Lab A = campus + WAN, Lab B = DC fabric)
# --------------------------------------------------------------------------
DEVICES = {
    # name        platform    role      site   mgmt-ip          loopback0
    "ISP-A":     dict(platform="vios",   role="isp",    site="WAN", mgmt="172.16.99.101", lo0="203.0.113.254", lab="A"),
    "ISP-B":     dict(platform="vios",   role="isp",    site="WAN", mgmt="172.16.99.102", lo0="198.51.100.254", lab="A"),
    "HCM-EDG1":  dict(platform="vios",   role="edge",   site="HCM", mgmt="172.16.99.11", lo0="10.10.255.1", isp="ISP-A", plane="A"),
    "HCM-EDG2":  dict(platform="vios",   role="edge",   site="HCM", mgmt="172.16.99.12", lo0="10.10.255.2", isp="ISP-B", plane="B"),
    "HCM-CORE1": dict(platform="viosl2", role="core",   site="HCM", mgmt="172.16.99.13", lo0="10.10.255.3"),
    "HCM-CORE2": dict(platform="viosl2", role="core",   site="HCM", mgmt="172.16.99.14", lo0="10.10.255.4"),
    "HCM-ACC1":  dict(platform="viosl2", role="access", site="HCM", mgmt="172.16.99.15", svi99="10.10.44.15"),
    "HCM-SRV1":  dict(platform="vios",   role="server", site="HCM", mgmt="172.16.99.16", ip="10.10.43.10"),
    "HAN-EDG1":  dict(platform="vios",   role="edge",   site="HAN", mgmt="172.16.99.21", lo0="10.20.255.1", isp="ISP-A", plane="A"),
    "HAN-EDG2":  dict(platform="vios",   role="edge",   site="HAN", mgmt="172.16.99.22", lo0="10.20.255.2", isp="ISP-B", plane="B"),
    "HAN-ACC1":  dict(platform="viosl2", role="access", site="HAN", mgmt="172.16.99.25", svi99="10.20.31.15"),
    "DAD-EDG1":  dict(platform="vios",   role="edge",   site="DAD", mgmt="172.16.99.31", lo0="10.30.255.1", isp="ISP-A", plane="A"),
    "DAD-EDG2":  dict(platform="vios",   role="edge",   site="DAD", mgmt="172.16.99.32", lo0="10.30.255.2", isp="ISP-B", plane="B"),
    "DAD-ACC1":  dict(platform="viosl2", role="access", site="DAD", mgmt="172.16.99.35", svi99="10.30.144.15"),
    # Lab B -- EVPN-VXLAN data-centre fabric (Arista vEOS)
    "DC-SPINE1": dict(platform="veos", role="spine", site="HCM", mgmt="172.16.99.41", lo0="10.10.191.1", lab="B"),
    "DC-SPINE2": dict(platform="veos", role="spine", site="HCM", mgmt="172.16.99.42", lo0="10.10.191.2", lab="B", optional=True),
    "DC-LEAF1":  dict(platform="veos", role="leaf",  site="HCM", mgmt="172.16.99.43", lo0="10.10.191.11", vtep="10.10.191.21", lab="B"),
    "DC-LEAF2":  dict(platform="veos", role="leaf",  site="HCM", mgmt="172.16.99.44", lo0="10.10.191.12", vtep="10.10.191.22", lab="B"),
}
for _d in DEVICES.values():
    _d.setdefault("lab", "A")


def lo0_v6(dev):
    """Loopback0 IPv6: <site /48>:ff00::<last octet of IPv4 loopback>/128."""
    d = DEVICES[dev]
    site = SITES[d["site"]]
    base = ip.IPv6Network(site["v6"]).network_address
    host = int(d["lo0"].split(".")[-1])
    return str(ip.IPv6Address(int(base) + (0xff00 << 64) + host))


# Routed point-to-point links inside sites: (site, A, A-if, B, B-if, v4/30, v6/64)
P2P_LINKS = [
    ("HCM", "HCM-EDG1", "Gi0/2", "HCM-CORE1", "Gi1/0", "10.10.254.0/30", "2001:db8:a010:fe01::/64"),
    ("HCM", "HCM-EDG1", "Gi0/3", "HCM-CORE2", "Gi1/0", "10.10.254.4/30", "2001:db8:a010:fe02::/64"),
    ("HCM", "HCM-EDG2", "Gi0/2", "HCM-CORE1", "Gi1/1", "10.10.254.8/30", "2001:db8:a010:fe03::/64"),
    ("HCM", "HCM-EDG2", "Gi0/3", "HCM-CORE2", "Gi1/1", "10.10.254.12/30", "2001:db8:a010:fe04::/64"),
    ("HCM", "HCM-EDG1", "Gi0/4", "HCM-EDG2", "Gi0/4", "10.10.254.16/30", "2001:db8:a010:fe05::/64"),
    ("HCM", "HCM-CORE1", "Vlan900", "HCM-CORE2", "Vlan900", "10.10.254.20/30", "2001:db8:a010:fe06::/64"),
    ("HAN", "HAN-EDG1", "Gi0/3", "HAN-EDG2", "Gi0/3", "10.20.254.0/30", "2001:db8:a020:fe01::/64"),
    ("DAD", "DAD-EDG1", "Gi0/3", "DAD-EDG2", "Gi0/3", "10.30.254.0/30", "2001:db8:a030:fe01::/64"),
]

# Customer <-> ISP links: (ISP, ISP-if, CE, CE-if, /30). ISP gets .1, CE gets .2
ISP_LINKS = [
    ("ISP-A", "Gi0/1", "HCM-EDG1", "Gi0/1", "203.0.113.0/30"),
    ("ISP-A", "Gi0/2", "HAN-EDG1", "Gi0/1", "203.0.113.4/30"),
    ("ISP-A", "Gi0/3", "DAD-EDG1", "Gi0/1", "203.0.113.8/30"),
    ("ISP-B", "Gi0/1", "HCM-EDG2", "Gi0/1", "198.51.100.0/30"),
    ("ISP-B", "Gi0/2", "HAN-EDG2", "Gi0/1", "198.51.100.4/30"),
    ("ISP-B", "Gi0/3", "DAD-EDG2", "Gi0/1", "198.51.100.8/30"),
]

# GRE-over-IPsec overlay tunnels: (number, A, B, v4/30, v6/64, transport plane)
TUNNELS = [
    (11, "HCM-EDG1", "HAN-EDG1", "10.0.0.0/30",  "2001:db8:a000:11::/64", "A"),
    (12, "HCM-EDG1", "DAD-EDG1", "10.0.0.4/30",  "2001:db8:a000:12::/64", "A"),
    (13, "HAN-EDG1", "DAD-EDG1", "10.0.0.16/30", "2001:db8:a000:13::/64", "A"),
    (21, "HCM-EDG2", "HAN-EDG2", "10.0.0.8/30",  "2001:db8:a000:21::/64", "B"),
    (22, "HCM-EDG2", "DAD-EDG2", "10.0.0.12/30", "2001:db8:a000:22::/64", "B"),
    (23, "HAN-EDG2", "DAD-EDG2", "10.0.0.20/30", "2001:db8:a000:23::/64", "B"),
]

# Layer-2 trunks: (A, A-if, B, B-if, port-channel or None)
TRUNKS = [
    ("HCM-CORE1", "Gi0/1", "HCM-CORE2", "Gi0/1", 1),
    ("HCM-CORE1", "Gi0/2", "HCM-CORE2", "Gi0/2", 1),
    ("HCM-CORE1", "Gi0/3", "HCM-ACC1", "Gi0/1", None),
    ("HCM-CORE2", "Gi0/3", "HCM-ACC1", "Gi0/2", None),
    ("HAN-EDG1", "Gi0/2", "HAN-ACC1", "Gi0/1", None),   # router-on-a-stick trunks
    ("HAN-EDG2", "Gi0/2", "HAN-ACC1", "Gi0/2", None),
    ("DAD-EDG1", "Gi0/2", "DAD-ACC1", "Gi0/1", None),
    ("DAD-EDG2", "Gi0/2", "DAD-ACC1", "Gi0/2", None),
]

# Access ports: (switch, if, endpoint, endpoint-if, data VLAN, voice VLAN)
ACCESS_PORTS = [
    ("HCM-ACC1", "Gi1/0", "PC-HCM-EXEC",  "eth0", 10, 40),
    ("HCM-ACC1", "Gi1/1", "PC-HCM-CORP",  "eth0", 12, 40),
    ("HCM-ACC1", "Gi1/2", "PC-HCM-GUEST", "eth0", 60, None),
    ("HCM-ACC1", "Gi1/3", "PC-HCM-PHONE", "eth0", 40, None),
    ("HCM-ACC1", "Gi2/0", "HCM-SRV1",     "Gi0/1", 80, None),
    ("HAN-ACC1", "Gi1/0", "PC-HAN-ENG",   "eth0", 20, 40),
    ("HAN-ACC1", "Gi1/1", "PC-HAN-PHONE", "eth0", 40, None),
    ("HAN-ACC1", "Gi1/2", "PC-HAN-GUEST", "eth0", 60, None),
    ("DAD-ACC1", "Gi1/0", "PC-DAD-LOG",   "eth0", 30, 40),
    ("DAD-ACC1", "Gi1/1", "PC-DAD-IOT",   "eth0", 50, None),
    ("DAD-ACC1", "Gi1/2", "PC-DAD-PHONE", "eth0", 40, None),
    ("DAD-ACC1", "Gi1/3", "PC-DAD-GUEST", "eth0", 60, None),
]

# --------------------------------------------------------------------------
# Lab B -- EVPN-VXLAN fabric
# --------------------------------------------------------------------------
DC = dict(
    asn=65011,
    vrf="TENANT-PROD", l3vni=50001,
    anycast_mac="00:1c:73:00:dc:01",
    vlans=[dict(vlan=110, name="DC_APP", vni=10110, v4="10.10.128.0/24"),
           dict(vlan=120, name="DC_DB",  vni=10120, v4="10.10.129.0/24")],
    # (spine, spine-if, leaf, leaf-if, /31)
    fabric_links=[
        ("DC-SPINE1", "Ethernet1", "DC-LEAF1", "Ethernet1", "10.10.190.0/31"),
        ("DC-SPINE1", "Ethernet2", "DC-LEAF2", "Ethernet1", "10.10.190.2/31"),
        ("DC-SPINE2", "Ethernet1", "DC-LEAF1", "Ethernet2", "10.10.190.4/31"),
        ("DC-SPINE2", "Ethernet2", "DC-LEAF2", "Ethernet2", "10.10.190.6/31"),
    ],
    hosts=[  # (leaf, leaf-if, host, vlan, ip)
        ("DC-LEAF1", "Ethernet3", "DC-H1", 110, "10.10.128.11"),
        ("DC-LEAF2", "Ethernet3", "DC-H2", 110, "10.10.128.12"),
        ("DC-LEAF2", "Ethernet4", "DC-H3", 120, "10.10.129.13"),
    ],
)

# --------------------------------------------------------------------------
# Lab sizing (EVE-NG RAM per template)
# --------------------------------------------------------------------------
RAM_MB = {"vios": 512, "viosl2": 768, "veos": 2048, "vpcs": 0}

# --------------------------------------------------------------------------
# Small helpers used by every renderer
# --------------------------------------------------------------------------
def hosts(prefix):
    return list(ip.ip_network(prefix).hosts())


def nth(prefix, n):
    """n-th usable address (1-based) of an IPv4/IPv6 prefix."""
    net = ip.ip_network(prefix)
    return str(net.network_address + n)


def mask(prefix):
    return str(ip.ip_network(prefix).netmask)


def wildcard(prefix):
    return str(ip.ip_network(prefix).hostmask)


def plen(prefix):
    return ip.ip_network(prefix).prefixlen


def site_subnet(site, vlan):
    for s in SUBNETS[site]:
        if s["vlan"] == vlan:
            return s
    raise KeyError((site, vlan))


def full_if(short):
    for k, v in (("Gi", "GigabitEthernet"), ("Lo", "Loopback"), ("Tu", "Tunnel"), ("Po", "Port-channel")):
        if short.startswith(k) and not short.startswith(v):
            return v + short[len(k):]
    return short


def lab_a_devices():
    return [n for n, d in DEVICES.items() if d["lab"] == "A"]


def endpoints():
    return [p[2] for p in ACCESS_PORTS if p[2].startswith("PC-")]
