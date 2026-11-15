---
name: idle-compute-detection
description: Assess Azure compute idleness and sizing using corroborated utilisation evidence. Use when investigating FinOps waste or rightsizing. Do not use to stop or resize live resources.
---

# Idle / oversized compute detection

Load the `finops-squad` skill, follow its preflight and its installed `references/safety-contract.md`.

Use real Azure Monitor metrics over a stated window. Never call a resource idle from a single data
point.

## When to use

- A `waste`-mode candidate needs an idle/not-idle verdict.
- A `rightsizing`-mode candidate needs a target SKU with headroom evidence.

## Inputs

| Source | Role |
|---|---|
| Azure MCP `monitor` (`metrics query`/`batchquery`) | avg/max/p95 CPU, memory, network, and rule-hit signals |
| `inventory.json` | Candidate resource list and current SKU |
| Stated observation window | Default 14 days minimum, hourly grain; prefer 30 days |

## Outputs

| Artifact / field | Result |
|---|---|
| `findings/waste.json` evidence | Idle verdict + the exact window/grain/metrics used |
| `findings/rightsizing.json` evidence | Target SKU + priced delta for an oversized candidate |

## Observation window

- Default: **14 days** minimum, hourly grain. Prefer 30 days to span weekly cycles.
- Record the exact window and grain in evidence.

## Thresholds (starting points — state them in the finding)

| Signal | Metric | Idle | Oversized (downsize candidate) |
|---|---|---|---|
| CPU | `Percentage CPU` avg | < 3% | p95 < 40% |
| CPU burst | `Percentage CPU` max | < 10% | — |
| Memory | `Available Memory Bytes` | consistently high free | high free headroom |
| Network | in/out bytes | ≈ 0 | low |

- **Idle** (all signals low): candidate for shutdown schedule or deallocation proposal.
- **Oversized** (steady low p95 with headroom): candidate for a smaller SKU.

## Method

1. Pull metrics via Azure MCP `monitor` (`metrics query`/`batchquery`). Use batch for many VMs.
2. Compute avg, max and p95; compare to thresholds.
3. For downsizes, pick a target SKU with headroom and price the delta.
4. For network/security appliances (firewalls, gateways), **never** rely on one bandwidth metric —
   follow [references/network-appliance-false-positive.md](references/network-appliance-false-positive.md)
   and corroborate with a second, independent signal before calling anything idle.

## What NOT to trust

- Short windows (< 7 days) or periods spanning maintenance/holidays.
- CPU alone — a DB VM can be memory/IO bound. Check multiple signals.
- A single traffic/bandwidth metric for network appliances — see the worked example in
  [references/network-appliance-false-positive.md](references/network-appliance-false-positive.md).
- Burstable (B-series) VMs: low average is by design; use credit metrics, not raw CPU.
- Production without owner sign-off → **T3**, analysis only.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Azure Monitor metrics overview | <https://learn.microsoft.com/en-us/azure/azure-monitor/essentials/data-platform-metrics> |
| Supported metrics for Microsoft.Compute/virtualMachines | <https://learn.microsoft.com/en-us/azure/azure-monitor/reference/supported-metrics/microsoft-compute-virtualmachines-metrics> |
| Azure Firewall metrics (Throughput, NetworkRuleHit) | <https://learn.microsoft.com/en-us/azure/firewall/metrics> |
| Azure Advisor performance/cost recommendations | <https://learn.microsoft.com/en-us/azure/advisor/advisor-reference-cost-recommendations> |
| B-series burstable VM credits | <https://learn.microsoft.com/en-us/azure/virtual-machines/sizes-b-series-burstable> |

### Key takeaways

- A single metric is never proof of idle — corroborate with at least one independent signal,
  always, not just for network appliances.
- High cost tells you where to look, not what to conclude.
- B-series "low average CPU" is by design, not evidence of oversizing.
