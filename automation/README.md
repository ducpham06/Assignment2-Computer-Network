# TVI automation (Step 9) — Python + Netmiko

```
automation/
├── tvi_auto.py          # backup / provision / verify / telemetry
├── inventory.yaml       # hosts, mgmt IPs, device_type, site, role (NO credentials)
├── vars/baseline.yaml   # AAA, NTP, syslog, banner, hardening payload
├── vars/vlans.yaml      # standard VLANs 10/20/30/99 + per-site extras
├── tests/               # offline tests with a fake device (pytest)
├── backups/             # <hostname>_<timestamp>_backup.cfg, _ipbrief.txt, _diff.txt
├── logs/automation.log  # every success and every SSH/auth/config error
└── telemetry/           # JSON snapshots from --task telemetry
```

## Install (on the EVE-NG VM or any host that can reach 172.16.99.0/24)

```bash
cd automation
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 -m pytest -q            # 8 offline tests, no lab needed
```

## Credentials — never in a file

```bash
export TVI_SSH_USER=tviadmin
read -s TVI_SSH_PASS && export TVI_SSH_PASS      # or leave unset and answer the getpass prompt
```

## Run

```bash
python3 tvi_auto.py --dry-run                      # print the payload per device, no SSH
python3 tvi_auto.py --task backup                  # snapshot every node (campus/WAN + DC fabric)
python3 tvi_auto.py --task all                     # pre-backup -> push -> write mem -> post-backup -> diff -> verify
python3 tvi_auto.py --task all --site HAN --role access
python3 tvi_auto.py --task verify                  # VLAN compliance only
python3 tvi_auto.py --task telemetry --role edge core
python3 tvi_auto.py --task telemetry --lab B       # vEOS fabric: EVPN peers + VTEPs (vEOS is backup/telemetry only)
```

Exit code is 1 if any device failed, so the script can run from cron/CI.

## Adding a VLAN programmatically

Edit `vars/vlans.yaml`:

```yaml
site_vlans:
  HAN:
    - {id: 25, name: AI_TRAINING}
```

then `python3 tvi_auto.py --task all --site HAN --role core access`.
