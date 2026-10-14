---
name: idle-compute-detection
description: Decide whether a VM, scale set or gateway is idle or oversized using utilization thresholds and sensible observation windows. Use for waste hunting and rightsizing.
---

# Idle / oversized compute detection

Use real Azure Monitor metrics over a stated window. Never call a resource idle from a single data
point.

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

## Network/security appliances (firewalls, gateways) — use rule/throughput metrics together

**Never call a firewall, NAT gateway, or VPN/ExpressRoute gateway idle from a bandwidth metric
alone.** Worked example from a live investigation: an Azure Firewall showed `Throughput` averaging
**0 bits/sec** over 7 days (daily grain) — on its own, that looked like a clean "idle, delete it"
candidate, especially since it was also the subscription's single largest cost line. But a second
metric, `NetworkRuleHit`, showed **~43,000 hits/day, every day** — the firewall was actively
evaluating real traffic the whole time. The `Throughput` average simply rounded down at daily
granularity because the traffic was small-packet/rule-evaluation volume, not bulk data transfer.
Concluding "idle" from `Throughput` alone would have produced a false-positive finding against a
production hub resource.

**Rule for this category:** before proposing any finding for a firewall, NAT gateway, VPN gateway,
or ExpressRoute gateway, pull **at least two independent signals** —
e.g. `Throughput`/`DataProcessed` **and** `NetworkRuleHit`/`ApplicationRuleHit`/connection-count —
and only conclude idle if **all** of them are near-zero across the whole window. A high cost alone
is never evidence of waste; it only tells you where to look.

## What NOT to trust

- Short windows (< 7 days) or periods spanning maintenance/holidays.
- CPU alone — a DB VM can be memory/IO bound. Check multiple signals.
- A single traffic/bandwidth metric for network appliances — see the firewall example above.
- Burstable (B-series) VMs: low average is by design; use credit metrics, not raw CPU.
- Production without owner sign-off → **T3**, analysis only.
