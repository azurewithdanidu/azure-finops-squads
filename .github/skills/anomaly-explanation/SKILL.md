---
name: anomaly-explanation
description: Explain a spend spike by decomposing the cost delta and correlating with activity. Use when costs jump and someone asks "why?".
---

# Anomaly explanation

Turn "spend went up" into "here is exactly what changed and why". Needs cost history
(`cost.query_spend`, ARM MCP); without it, limit to activity correlation and say cost deltas are
unavailable.

## When to use

- A spend spike/dip is reported or detected and needs a concrete, evidenced explanation.

## Inputs

| Source | Role |
|---|---|
| `arm.query_costs` (baseline + observed period) | The delta to decompose |
| `monitor` activity logs, Resource Graph timestamps | Correlated deployments/SKU changes/scale events |

## Outputs

| Artifact / field | Result |
|---|---|
| `findings/anomalies.json` entry (`type: "anomaly"`) | Baseline vs observed, delta breakdown, correlated activity |
| `investigations/<slug>.json` | Written instead, when the hypothesis doesn't hold up |

## Method

1. **Detect**: compare the period to a baseline (prior period / trailing average) by service,
   resource group, and tag. Flag deltas beyond a threshold (e.g. > 20% or > a $ floor).
2. **Decompose**: attribute the delta to specific service / resource / meter. A full worked example
   is in [references/worked-example.md](references/worked-example.md).
3. **Correlate**: line up the delta with activity — deployments, SKU changes, scale-out, new
   resources, region moves — using `monitor` activity logs and Resource Graph timestamps.
4. **Classify**: expected (planned rollout) vs unexpected (leak, runaway job, misconfig).

Usually **T0** (explanatory). If it reveals a concrete reducible cost (e.g. a forgotten load test
cluster), set a real `estimatedMonthlySaving`; otherwise 0, labelled.

## Pitfalls

- Price or currency changes can masquerade as anomalies — rule them out.
- Proration at month boundaries causes apparent spikes — align windows.
- Correlation isn't causation; present the activity evidence, don't assert intent.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Cost Management anomaly detection | https://learn.microsoft.com/en-us/azure/cost-management-billing/understand/analyze-unexpected-charges |
| Activity log overview | https://learn.microsoft.com/en-us/azure/azure-monitor/essentials/activity-log |
| Cost Management data latency | https://learn.microsoft.com/en-us/azure/cost-management-billing/automate/ratelimits-cost-management-api-data-latency |

### Key takeaways

- Decompose to the resource/meter level before correlating — "Compute went up" isn't an
  explanation, "3 new D4s_v5 VMs tagged to release X" is.
- An unexplained spike that doesn't correlate with any activity is still honest to report as
  unexplained — don't force a correlation that isn't there.
