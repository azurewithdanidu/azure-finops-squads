---
name: orphaned-resource-detection
description: Detect orphaned Azure resources — unattached disks, unassociated public IPs, empty NICs, stale snapshots, idle gateways. Use when hunting waste that is safe to remove.
---

# Orphaned resource detection

Orphans are resources that incur cost while serving nothing. Most are **T1** (delete via PR with a
rollback note); some (NAT/VPN/App Gateway) need extra care.

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

1. Find candidates with Resource Graph ([resource-graph-kql](../resource-graph-kql/SKILL.md)).
2. Confirm "orphan" with a time dimension — unattached **and** no recent attach activity in the
   window (check activity logs where available). State the window in evidence.
3. Price the monthly cost (disk size×SKU rate, public IP hourly rate, gateway SKU) via
   [price-basis-handling](../price-basis-handling/SKILL.md).
4. Match to IaC ([iac-matching](../iac-matching/SKILL.md)); set tier
   ([risk-tier-assessment](../risk-tier-assessment/SKILL.md)).

## Pitfalls

- Some orphans are deliberate (warm spares, DR). Check tags like `keep`, `dr`, `do-not-delete`.
- A disk attached to a *deallocated* VM is **not** an orphan — don't propose deleting it.
- Gateways with low-but-nonzero traffic may still be needed; prefer T2 and ask.
