---
name: finops-reporting
description: Produce Azure FinOps executive reports, backlog, ledger, KPIs and retrospectives. Use when reporting or refreshing an audit run. Do not use for generic dashboards or cost estimates without evidence.
---

# FinOps reporting

Two audiences, one truth. Keep basis and confidence on every number.

Load the `finops-squad` skill and follow its entry preflight and binding installed
`references/safety-contract.md`, including when invoked directly.
Read artifacts only; never query Azure or write run-status.md. Resolve bundled scripts from the
installed entry skill and use `python -B` with absolute consumer run paths, as the entry explains.

## When to use

- The Visualizer is building `reports/*.md` or `savings-ledger.json` from a run's artifacts.

## Inputs

| Source | Role |
|---|---|
| `spend.json`, `findings/*.json`, `verification/*.json` | All the numbers a report cites |
| `inventory.json`, `advisor.json`, `plan.md`, `investigations/*.json` | Discovery context, ranking and checked-but-retracted hypotheses |
| `.finops/config.json` | Default currency/locale |
| Prior `plan.md` and `reports/retrospective.md` | Optional earlier runs sharing the iteration ID |

## Outputs

| Artifact / field | Result |
|---|---|
| `reports/executive-summary.md` | Spend trend, estimated vs realised saving, headline findings, status |
| `reports/engineer-backlog.md` | Ranked, actionable finding table |
| `reports/savings-ledger.json` | Estimated vs realised, by finding type, grouped by currency |
| `reports/kpis.json` | Named KPI set (tagging compliance, allocation coverage, savings opportunity, realised rate, anomaly trend) — see KPI set below |
| `reports/retrospective.md` | Only when an `iteration.md` brief exists — see Retrospective below |

## Executive summary (`executive-summary.md`)

- Spend trend over the window (total + top services), in AUD / en-AU by default.
- **Estimated** monthly saving opportunity and **Realised** monthly saving — shown as two separate
  totals, never merged. A full worked excerpt is in
  [references/worked-example.md](references/worked-example.md).
- Headline findings (3–5), each with tier and confidence.
- Current status: how many proposed / approved / PR-open / merged / verified.
- Summarise evidence-led investigations that were checked but did not become findings.

## Engineer backlog (`engineer-backlog.md`)

- Ranked table: id, type, tier, resource, est. saving + basis, confidence, effort, iacMatch, status.
- Group by tier or by type; make each row actionable.

## Savings ledger (`savings-ledger.json`)

- Generate with `python -B "<absolute-entry-skill-dir>/scripts/ledger.py" "<absolute-run>"`.
- Separates estimated vs realised, by finding type, **and by currency** — `ledger["currency"]` /
  `ledger["totals"]` / `ledger["byType"]` reflect only the primary (most-findings) currency;
  `ledger["mixedCurrencies"]` is `true` whenever more than one currency is present, and
  `ledger["byCurrency"]` carries every currency's own totals. Never report the top-level totals as
  if they covered a mixed-currency run — check `mixedCurrencies` first.

## KPI set (`kpis.json`)

Generate after the ledger with `python -B "<absolute-entry-skill-dir>/scripts/kpis.py" "<absolute-run>" --runs-dir "<absolute-runs-dir>"`. Per the FinOps
Framework's [KPIs & Benchmarking capability](https://www.finops.org/framework/capabilities/kpis-benchmarking/)
("a curated, well-documented set of KPIs... regularly reviewed for relevance" — not raw, unnamed
totals), this is a small, named set rather than every number the run produced:

| KPI | What it measures | Honesty rule |
|---|---|---|
| `taggingCompliance` | % of resources with **every** required tag, vs the Framework's named >90% target | `method: "unavailable"` with a `note` when `inventory.json` lacks the data — never guessed |
| `allocationCoverage` | % of spend attributable to resource groups with full tag coverage | Same — requires both a spend breakdown and `resourceGroupTags`; states exactly which is missing |
| `estimatedSavingsOpportunity` | Primary-currency total from the savings ledger | Notes when the run is mixed-currency rather than silently reporting a partial total |
| `realisedSavingsRate` | realised ÷ estimated, as a % | 0% (not "unavailable") when nothing has been estimated yet — that's a true zero, not missing data |
| `anomalyCount` | This run's anomaly count, trended vs the nearest earlier run | `trend: "unavailable"` with no earlier run to compare against — never assumes "flat" by default |

Every KPI's `method`/`trend` field states exactly how it was computed (or why it couldn't be) —
report that provenance alongside the number, the same as a finding's evidence.

## Retrospective (`retrospective.md`, only with an iteration brief)

Only written when `.finops/runs/<id>/iteration.md` exists for this run (or a prior run sharing its
`iterationId`) — use `iteration-brief`. Structure:

1. **Goal progress** — baseline → current value for each stated goal, against its target.
2. **Realised vs estimated**, scoped to this iteration's findings (not the whole run's ledger).
3. **Blockers**, framed as process lessons (e.g. "blocked on IaC repo access"), never as a failed
   saving.
4. **Repeated vs resolved findings** since the prior run in this iteration: use
   `python -B "<absolute-entry-skill-dir>/scripts/compare_runs.py" "<absolute-earlier-run>" "<absolute-later-run>"` to match by type and resource ID.
   The comparison describes presence across runs, not proof that a missing finding was remediated;
   check lifecycle and verification artifacts before claiming a saving was realised.
5. **1-2 candidate next goals**, grounded only in what's still open from this iteration.

## FOCUS-aligned terminology

Use consistent terms: *billed cost*, *effective cost*, *amortized cost*, *list unit price*,
*contracted unit price*, *resource*, *service*, *region*, *tag/allocation*. Prefer these over
ad-hoc labels. **This is a terminology choice, not a data-format claim** — finops-squad's artifacts
are Azure-shaped JSON (the finding/verification schemas), not FOCUS-formatted cost-and-usage
records. Never describe a report or artifact as "FOCUS compliant" or "FOCUS data" unless it has
actually been mapped and validated against the [FOCUS specification](https://focus.finops.org/) —
using FOCUS-aligned words is not the same claim as emitting FOCUS-shaped data.

## Honesty rules

- Never present a list-price estimate as realised. Realised comes only from `verification/*.json`
  (`confirmed`/`partial`).
- Attempt `cost.query_spend` (`arm.query_costs`) before assuming it's unavailable. If spend data is
  genuinely unavailable (the call actually failed), state "spend data unavailable: `<reason>`"
  rather than inventing a total or trend. Report the **currency the API actually returned** —
  never silently convert it to match the report's configured default currency.
- Show the price `basis` and `confidence` next to each saving.
- **Never sum amounts across different currencies.** Check every number's own currency before
  adding it to a total; report mixed currencies side by side, not blended.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| FinOps Open Cost and Usage Specification (FOCUS) | <https://focus.finops.org/> |
| Cost Management reporting exports | <https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-export-acm-data> |

### FinOps Foundation

| Topic | Link |
|---|---|
| Reporting & Analytics capability (named KPIs, 90% tagging target, allocation coverage output) | <https://www.finops.org/framework/capabilities/reporting-analytics/> |
| KPIs & Benchmarking capability (curated, named KPI sets) | <https://www.finops.org/framework/capabilities/kpis-benchmarking/> |

### Key takeaways

- Estimated and realised are two numbers, always — a reader should never have to guess which one
  they're looking at.
- A $0 saving (e.g. a tagging-gap finding) is reported as $0, not omitted — omission reads as
  inflation by hindsight.
- A named, small KPI set beats a wall of raw totals — pick a handful (per the Framework's own
  "start small" guidance) and keep them consistent across runs so trends are actually comparable.
