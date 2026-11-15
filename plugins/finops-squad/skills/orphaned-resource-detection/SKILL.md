---
name: orphaned-resource-detection
description: Detect orphaned Azure disks, IPs, NICs and snapshots for FinOps waste analysis. Use when investigating unused resources. Do not use to delete or mutate Azure resources.
---

# Orphaned resource detection

Load the `finops-squad` skill, follow its preflight and its installed `references/safety-contract.md`.

Orphans are resources that incur cost while serving nothing. Most are **T1** (delete via PR with a
rollback note); some (NAT/VPN/App Gateway) need extra care.

## When to use

- `waste`-mode is looking for resources that cost money but serve no live workload.

## Inputs

| Source | Role |
|---|---|
| `resource-graph-kql` queries | Candidate disks/IPs/NICs/snapshots |
| Activity logs (where available) | Confirms "no recent attach activity", not just current state |

## Outputs

| Artifact / field | Result |
|---|---|
| `findings/waste.json` entry | Priced, tiered, IaC-matched orphan finding — see the worked example below |

## Targets and signals

| Resource | Orphan signal | Typical tier |
|---|---|---|
| Managed disk | `properties.diskState == 'Unattached'` | T1 |
| Public IP | `ipConfiguration == null` and `natGateway == null` | T1 |
| NIC | `virtualMachine == null` | T1 |
| Snapshot | age > N days, source disk gone | T1 |
| Disk (attached to deallocated VM) | VM deallocated long-term | T2 (review) |
| NAT / VPN / App Gateway | no traffic over window (metrics ≈ 0) | T2 |

## Method

1. Find candidates with Resource Graph (use `resource-graph-kql`).
2. Confirm "orphan" with a time dimension — unattached **and** no recent attach activity in the
   window (check activity logs where available). State the window in evidence. A concrete evidence
   entry is in [references/worked-example.md](references/worked-example.md).
3. Price the monthly cost (disk size×SKU rate, public IP hourly rate, gateway SKU) via
   `price-basis-handling`.
4. Match to IaC (`iac-matching`); set tier using `risk-tier-assessment`.

## Pitfalls

- Some orphans are deliberate (warm spares, DR). Check tags like `keep`, `dr`, `do-not-delete`.
- A disk attached to a *deallocated* VM is **not** an orphan — don't propose deleting it.
- Gateways with low-but-nonzero traffic may still be needed; prefer T2 and ask.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Find and delete unattached Azure managed disks | <https://learn.microsoft.com/en-us/azure/virtual-machines/disks-find-unattached-portal> |
| Public IP addresses overview | <https://learn.microsoft.com/en-us/azure/virtual-network/ip-services/public-ip-addresses> |
| Azure Activity log | <https://learn.microsoft.com/en-us/azure/azure-monitor/essentials/activity-log> |

### Key takeaways

- "Currently unattached" is not evidence by itself — pair it with a duration and an activity-log
  check for recent attach events, per the worked example.
- A deallocated VM's disk is a cost-reduction opportunity for the VM, not an orphan finding for the
  disk — don't conflate the two.
