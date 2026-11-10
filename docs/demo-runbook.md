# 15-minute live demo runbook

Before the session: Lab A fully booted for 10+ minutes, all tests in `test-plan.md` passed once,
terminals open on HCM-EDG1, HCM-CORE1, HCM-ACC1, HAN-EDG1, PC-HCM-CORP, PC-HAN-ENG and the EVE VM
(automation). Put the diagrams on a second screen. Rehearse once with a timer.

| Time | Who | What to show | Commands |
|---|---|---|---|
| 0:00–2:00 | Member 1 | Business problem -> architecture (logical + routing diagrams) | — |
| 2:00–5:00 | Member 2 | Underlay & overlay are up | HCM-CORE1 `show ip ospf nei`; HCM-EDG1 `show bgp ipv4 uni sum`, `show crypto ikev2 sa`, `show ip route bgp` |
| 5:00–7:30 | Member 2 | End-to-end + direct branch path + local breakout + isolation | PC-HAN-ENG `trace` to HCM-CORP and DAD-LOG; `ping 192.0.2.10`; HAN-EDG1 `show ip nat tr`; PC-HCM-GUEST `ping 10.10.43.10` (fails) |
| 7:30–11:00 | Member 3 | **Failover**: PC-HCM-CORP `ping <PC-DAD-LOG> -t`; stop HCM-CORE1 in EVE; show `show standby brief` on CORE2; count lost pings; start CORE1 again. Then PC-HAN-ENG `ping <PC-HCM-CORP> -t`, HAN-EDG1 `int gi0/1` `shut` -> ~15 s -> traffic back via plane B; `no shut` | see test-plan F3, F4 |
| 11:00–13:30 | Member 4 | **Automation**: `python3 tvi_auto.py --dry-run --site HAN`; uncomment VLAN 25 AI_TRAINING in `vars/vlans.yaml`; `python3 tvi_auto.py --task all --role core access`; open the diff file and `logs/automation.log`; HAN-ACC1 `show vlan brief` | |
| 13:30–15:00 | All | QoS counters (`show policy-map int gi0/1` on HCM-EDG1), questions | |

Fallbacks: if a node hangs, keep talking from the evidence screenshots in the report and restart it
in the background. Never run `--task all` for the first time during the demo.

Remember the grading note: anything the report claims (especially failover) must be reproducible live.
