# `query_costs` parameter reference

Full, observed parameter behaviour for `arm.query_costs` (and the AKS-specific variant), kept here
so `SKILL.md` can stay focused on the method.

## Parameters

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

## AKS cost (`arm.query_aks_costs`)

Subscription scope only — no resource-group or billing scopes. Supports breakdowns by
Cluster/Namespace/UtilizationBucket/ServiceCategory. Same ~92-day lookback cap, 100-row default,
5000-row max.

## Rate limits & caching

- Cost Management APIs throttle aggressively. Batch dimensions in one query where possible.
- Cache results within a run; don't re-query the same window per finding.
- On HTTP 429 or a throttling error, back off exponentially and record the retry in notes.
