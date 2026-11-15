---
name: cost-query-patterns
description: Query Azure spend for FinOps evidence, with rate limits and unavailable-data handling. Use when building spend.json or pricing a finding. Do not use for generic Azure operations.
---

# Cost query patterns

Load the `finops-squad` skill, follow its preflight and its installed `references/safety-contract.md`.

Discover the host's available spend capability (for example `arm.query_costs`); tools are not
guaranteed. See `references/capability-map.md` in the installed `finops-squad` skill. Attempt the
available query before treating spend as unavailable, and record a genuine missing tool or error.

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
| `spend.json` `daily` | Daily cost series (top 10 services + Other, `dailyTotal`), reconciled against the totals — see "Daily series" below |
| `{"status": "unavailable", "reason": ...}` | Honest fallback when the call genuinely fails |
| `estimatedMonthlySaving.basis` input | Currency/rate context passed to `price-basis-handling` |

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
   available) — use `price-basis-handling`.

## Daily series (required when spend is available)

After the aggregate call(s) succeed, make **one more** `arm.query_costs` call to capture cost per
day, so reports can detect events (a service that stopped billing, a step change, a spike).
It reuses the aggregate call's window, metric and currency.

Check the host's query schema; the following is an example of a daily query, not a guarantee of
tool availability or successful access.

1. **Call** (same `scope`, `from`, `to` and `metric` as the aggregate call):

   | Param | Value |
   |---|---|
   | `scope` | `/subscriptions/<id>` |
   | `timeframe` | `Custom` with `from` / `to` identical to the aggregate call |
   | `granularity` | `Daily` |
   | `groupBy` | `ServiceName` |
   | `metric` | the same metric as the aggregate call (e.g. `Cost`) |
   | `top` | `5000` |

2. **Normalise each returned row** to `{date, service, cost}`. The API reports the day as an
   integer such as `20261014`; write it as `"2026-10-14"`. Keep the returned currency.
3. **Truncation.** If the call returned exactly 5000 rows it hit the limit: set
   `daily.truncated: true` and keep what you received. Never extrapolate missing rows.
4. **Top 10 plus Other.** Rank services by their total over the window. Keep the top 10 as their
   own `series` rows. Add every remaining service together, per day, as rows with
   `"service": "Other"` (omit `Other` if there are no remaining services). Omit rows whose cost is
   zero.
5. **`dailyTotal`.** One entry `{date, cost}` for **every** date from `from` to `to` inclusive
   (cost `0` for a day with no spend). For each date the `series` costs must add up to that day's
   `dailyTotal`.
6. **`provisionalFrom`** = `to` minus 2 days, i.e. the first of the last three days. Cost data for
   those days is still settling (it can lag by up to ~3 days), so event detection ignores them.
7. **Reconcile** the sum of `dailyTotal` against the aggregate total (`totalLastMonth`). They must
   agree within 1%. If they do not: confirm the window, metric and currency are identical in both
   calls, re-query once, and if they still differ record the figures in `daily.reconciliation`
   (`dailyTotalSum`, `aggregateTotal`, `deltaPct`). **Never scale, round or adjust numbers to
   force a match.**
8. **Write the block** into `spend.json` beside the aggregates (which keep `"granularity": "None"`):

   ```json
   "daily": {
     "granularity": "Daily",
     "groupBy": "ServiceName",
     "metric": "Cost",
     "currency": "USD",
     "from": "2026-07-16",
     "to": "2026-10-14",
     "provisionalFrom": "2026-10-12",
     "truncated": false,
     "series": [
       { "date": "2026-07-16", "service": "Azure Firewall", "cost": 15.82 },
       { "date": "2026-07-16", "service": "Other", "cost": 21.4 }
     ],
     "dailyTotal": [ { "date": "2026-07-16", "cost": 98.37 } ]
   }
   ```

   `daily.currency` must equal the aggregate `currency`. Never convert currency.
9. **If the Daily call genuinely fails** (tool error, throttling after back-off), omit `daily` and
   record the real error in `inventory.json` as
   `"enrichmentSkipped": [{ "field": "daily", "reason": "<the error>" }]`. Do not fabricate a
   series.
10. **Validate** before hand-off: `python -B "<absolute-entry-skill-dir>/scripts/validate_discovery.py" "<absolute-run>" --strict`.

## If `cost.query_spend` is genuinely unavailable

Only after actually attempting the call and having it fail (tool not present in this host, auth
error, etc.) — do **not** fabricate numbers. Write:

```json
{ "status": "unavailable", "reason": "<the real error you got>", "capturedAt": "<iso>" }
```

and proceed with waste/utilization findings that don't require spend totals.

## Pitfalls

- Cost data lags (often 8–24h for recent days; up to ~3 days to settle). State the window, and
  mark the last three days as provisional (`daily.provisionalFrom`).
- Daily rows hit the 5000-row cap on long windows with many services: record `truncated`,
  never guess the missing rows.
- Amortized vs actual cost differ for commitments — pick one `metric` and label it.
- Tag-based cost needs tags to exist at spend time; retroactive tagging does not reallocate
  history — and tags cannot be used as a `groupBy` dimension in `query_costs` anyway.
- A single day's or week's cost figure is not evidence of waste by itself — correlate with
  resource state/utilization (use `idle-compute-detection`).

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Cost Management Query REST API | <https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage> |
| Understand Cost Management data | <https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/understand-cost-mgt-data> |
| Group and filter options | <https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/group-filter> |
| Cost Management errors and throttling | <https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/cost-management-error-codes> |
| AKS cost analysis | <https://learn.microsoft.com/en-us/azure/aks/cost-analysis> |

### Key takeaways

- Attempt an available spend query before declaring spend data unavailable; record the error or
  missing capability.
- Tags are never a valid `groupBy` dimension; tag-based cost needs a post-hoc join against
  inventory tags instead.
- Treat cost data as settling for ~3 days — a same-day total is provisional, not a verdict.
