---
name: finops-reporting
description: Structure FinOps reports for executives and engineers using FOCUS-aligned terminology, with honest estimate-vs-realised labelling. Use when the Visualizer builds reports.
---

# FinOps reporting

Two audiences, one truth. Keep basis and confidence on every number.

## When to use

- The Visualizer is building `reports/*.md` or `savings-ledger.json` from a run's artifacts.

## Inputs

| Source | Role |
|---|---|
| `spend.json`, `findings/*.json`, `verification/*.json` | All the numbers a report cites |
| `.finops/config.json` | Default currency/locale |

## Outputs

| Artifact / field | Result |
|---|---|
| `reports/executive-summary.md` | Spend trend, estimated vs realised saving, headline findings, status |
| `reports/engineer-backlog.md` | Ranked, actionable finding table |
| `reports/savings-ledger.json` | Estimated vs realised, by finding type, grouped by currency |
| `reports/retrospective.md` | Only when an `iteration.md` brief exists — see Retrospective below |

## Executive summary (`executive-summary.md`)

- Spend trend over the window (total + top services), in AUD / en-AU by default.
- **Estimated** monthly saving opportunity and **Realised** monthly saving — shown as two separate
  totals, never merged. A full worked excerpt is in
  [references/worked-example.md](references/worked-example.md).
- Headline findings (3–5), each with tier and confidence.
- Current status: how many proposed / approved / PR-open / merged / verified.

## Engineer backlog (`engineer-backlog.md`)

- Ranked table: id, type, tier, resource, est. saving + basis, confidence, effort, iacMatch, status.
- Group by tier or by type; make each row actionable.

## Savings ledger (`savings-ledger.json`)

- Generate with `python scripts/ledger.py .finops/runs/<id>/`.
- Separates estimated vs realised, by finding type, **and by currency** — `ledger["currency"]` /
  `ledger["totals"]` / `ledger["byType"]` reflect only the primary (most-findings) currency;
  `ledger["mixedCurrencies"]` is `true` whenever more than one currency is present, and
  `ledger["byCurrency"]` carries every currency's own totals. Never report the top-level totals as
  if they covered a mixed-currency run — check `mixedCurrencies` first.

## Retrospective (`retrospective.md`, only with an iteration brief)

Only written when `.finops/runs/<id>/iteration.md` exists for this run (or a prior run sharing its
`iterationId`) — see [iteration-brief](../iteration-brief/SKILL.md). Structure:

1. **Goal progress** — baseline → current value for each stated goal, against its target.
2. **Realised vs estimated**, scoped to this iteration's findings (not the whole run's ledger).
3. **Blockers**, framed as process lessons (e.g. "blocked on IaC repo access"), never as a failed
   saving.
4. **Repeated vs resolved findings** since the prior run in this iteration — reuse
   `run-status.md`'s record of what's still open per
   [run-orchestration](../run-orchestration/SKILL.md).
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
| FinOps Open Cost and Usage Specification (FOCUS) | https://focus.finops.org/ |
| Cost Management reporting exports | https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-export-acm-data |

### Key takeaways

- Estimated and realised are two numbers, always — a reader should never have to guess which one
  they're looking at.
- A $0 saving (e.g. a tagging-gap finding) is reported as $0, not omitted — omission reads as
  inflation by hindsight.
