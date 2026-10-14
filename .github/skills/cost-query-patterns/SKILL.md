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

## `query_costs` parameters (real, as observed)

| Param | Notes |
|---|---|
| `scope` | `/subscriptions/<id>` (not a tenant ID). |
| `timeframe` | `MonthToDate` (default), `BillingMonthToDate`, `TheLastMonth`, `TheLastBillingMonth`, `WeekToDate`, `TheCurrentMonth`, or `Custom` (with `from`/`to`). |
| `from` / `to` | `YYYY-MM-DD`; supplying both auto-selects `Custom`. |
| `granularity` | `None` (default, totals — fastest), `Daily`, `Monthly`. |
| `groupBy` | Comma-separated, **max 5 dimensions** (e.g. `ResourceGroupName,ServiceName`). **Tags are not supported** for grouping. |
| `filterDimension` / `filterValues` | Must be supplied together. Values must exactly match the API's canonical names. |
| `metric` | `PreTaxCost` (default), `Cost`, `AmortizedCost`, `CostUSD`, `PreTaxCostUSD`, `UsageQuantity`. |
| `sortBy` / `sortDirection` | Defaults to the cost metric, descending. |
| `top` | 1–5000, default 100. |

**Hard limits:** lookback capped at ~92 days (older `from` dates are rejected); more than ~10
subscriptions in one scope should be narrowed with the user first — the upstream Cost Management
API throttles and bursty fan-out returns rate-limit errors.

## Method

1. Define the window and grain from `.finops/config.json` (default: last 3 full months, Monthly).
2. Call `arm.query_costs` grouped by the dimension you need: `ServiceName`, `ResourceGroupName`,
   `ResourceId`, or a meter dimension. For a quick total, use `granularity=None` (fastest).
3. **Record the currency the API actually returns** — it reflects the subscription's billing
   currency and may not match your reports' default locale currency (e.g. it may return USD even
   if `.finops/config.json` defaults reports to AUD). Never silently convert or assume.
4. Record the price `basis` (actual for EA/MCA/CSP/PAYG actuals; list-price if only retail is
   available) — see [price-basis-handling](../price-basis-handling/SKILL.md).

## AKS cost

Use `arm.query_aks_costs` (subscription scope only — no resource-group/billing scopes) for
Cluster/Namespace/UtilizationBucket/ServiceCategory breakdowns. Same ~92-day lookback cap, 100-row
default, 5000-row max.

## If `cost.query_spend` is genuinely unavailable

Only after actually attempting the call and having it fail (tool not present in this host, auth
error, etc.) — do **not** fabricate numbers. Write:

```json
{ "status": "unavailable", "reason": "<the real error you got>", "capturedAt": "<iso>" }
```

and proceed with waste/utilization findings that don't require spend totals.

## Rate limits & caching

- Cost Management APIs throttle aggressively. Batch dimensions in one query where possible.
- Cache results within a run; don't re-query the same window per finding.
- On HTTP 429 or a throttling error, back off exponentially and record the retry in notes.

## Pitfalls

- Cost data lags (often 8–24h for recent days; up to ~3 days to settle). State the window.
- Amortized vs actual cost differ for commitments — pick one `metric` and label it.
- Tag-based cost needs tags to exist at spend time; retroactive tagging does not reallocate
  history — and tags cannot be used as a `groupBy` dimension in `query_costs` anyway.
- A single day's or week's cost figure is not evidence of waste by itself — correlate with
  resource state/utilization (see [idle-compute-detection](../idle-compute-detection/SKILL.md)).
