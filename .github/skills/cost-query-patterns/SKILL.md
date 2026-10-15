---
name: cost-query-patterns
description: Query Azure spend by service, resource group, tag and time grain, handling rate limits and the no-cost-tool fallback. Use when building spend.json or pricing a finding.
---

# Cost query patterns

Spend data comes from the **`arm` tool's `query_costs` command** (live-verified working, no extra
config needed in this agent host — see [mcp-capability-map.md](../../../docs/mcp-capability-map.md)
for the full correction history). **Always attempt `arm.query_costs` first.** Only treat
`cost.query_spend` as unavailable if the call itself genuinely fails in your environment.

## When to use

- Building `spend.json` (by service / resource group / resource / meter).
- Establishing a baseline for a finding or for anomaly detection.

## Inputs

| Source | Role |
|---|---|
| `.finops/config.json` | Default window and grain when the user hasn't stated one |
| `arm.query_costs` | Primary spend-by-dimension source |
| `arm.query_aks_costs` | AKS-specific cluster/namespace cost breakdown |

## Outputs

| Artifact / field | Result |
|---|---|
| `spend.json` | Spend totals/breakdowns with recorded currency and window |
| `{"status": "unavailable", "reason": ...}` | Honest fallback when the call genuinely fails |
| `estimatedMonthlySaving.basis` input | Currency/rate context passed to [price-basis-handling](../price-basis-handling/SKILL.md) |

## Method

1. Define the window and grain from `.finops/config.json` (default: last 3 full months, Monthly).
2. Call `arm.query_costs` grouped by the dimension you need: `ServiceName`, `ResourceGroupName`,
   `ResourceId`, or a meter dimension. For a quick total, use `granularity=None` (fastest). Full
   parameter behaviour (limits, defaults, AKS variant) is in
   [references/cost-query-parameters.md](references/cost-query-parameters.md).
3. **Record the currency the API actually returns** — it reflects the subscription's billing
   currency and may not match your reports' default locale currency (e.g. it may return USD even
   if `.finops/config.json` defaults reports to AUD). Never silently convert or assume.
4. Record the price `basis` (actual for EA/MCA/CSP/PAYG actuals; list-price if only retail is
   available) — see [price-basis-handling](../price-basis-handling/SKILL.md).

## If `cost.query_spend` is genuinely unavailable

Only after actually attempting the call and having it fail (tool not present in this host, auth
error, etc.) — do **not** fabricate numbers. Write:

```json
{ "status": "unavailable", "reason": "<the real error you got>", "capturedAt": "<iso>" }
```

and proceed with waste/utilization findings that don't require spend totals.

## Pitfalls

- Cost data lags (often 8–24h for recent days; up to ~3 days to settle). State the window.
- Amortized vs actual cost differ for commitments — pick one `metric` and label it.
- Tag-based cost needs tags to exist at spend time; retroactive tagging does not reallocate
  history — and tags cannot be used as a `groupBy` dimension in `query_costs` anyway.
- A single day's or week's cost figure is not evidence of waste by itself — correlate with
  resource state/utilization (see [idle-compute-detection](../idle-compute-detection/SKILL.md)).

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Cost Management Query REST API | https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage |
| Understand Cost Management data | https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/understand-cost-mgt-data |
| Group and filter options | https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/group-filter |
| Cost Management rate limits | https://learn.microsoft.com/en-us/azure/cost-management-billing/automate/ratelimits-cost-management-api-data-latency |
| AKS cost analysis | https://learn.microsoft.com/en-us/azure/aks/cost-analysis |

### Key takeaways

- `arm.query_costs` is live-verified with no extra configuration — try it before declaring spend
  data unavailable, every time.
- Tags are never a valid `groupBy` dimension; tag-based cost needs a post-hoc join against
  inventory tags instead.
- Treat cost data as settling for ~3 days — a same-day total is provisional, not a verdict.
