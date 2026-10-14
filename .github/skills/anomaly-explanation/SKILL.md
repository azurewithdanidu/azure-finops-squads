---
name: anomaly-explanation
description: Explain a spend spike by decomposing the cost delta and correlating with activity. Use when costs jump and someone asks "why?".
---

# Anomaly explanation

Turn "spend went up" into "here is exactly what changed and why". Needs cost history
(`cost.query_spend`, ARM MCP); without it, limit to activity correlation and say cost deltas are
unavailable.

## Method

1. **Detect**: compare the period to a baseline (prior period / trailing average) by service,
   resource group, and tag. Flag deltas beyond a threshold (e.g. > 20% or > a $ floor).
2. **Decompose**: attribute the delta to specific service / resource / meter. "Compute +$420,
   driven by 3 new D8s_v5 VMs in rg-prod."
3. **Correlate**: line up the delta with activity — deployments, SKU changes, scale-out, new
   resources, region moves — using `monitor` activity logs and Resource Graph timestamps.
4. **Classify**: expected (planned rollout) vs unexpected (leak, runaway job, misconfig).

## Output

A `type: "anomaly"` finding with evidence (baseline vs observed, delta breakdown, correlated
activity). Usually **T0** (explanatory). If it reveals a concrete reducible cost (e.g. a forgotten
load test cluster), set a real `estimatedMonthlySaving`; otherwise 0, labelled.

## Pitfalls

- Price or currency changes can masquerade as anomalies — rule them out.
- Proration at month boundaries causes apparent spikes — align windows.
- Correlation isn't causation; present the activity evidence, don't assert intent.
