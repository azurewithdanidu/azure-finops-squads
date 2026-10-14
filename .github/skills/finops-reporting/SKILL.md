---
name: finops-reporting
description: Structure FinOps reports for executives and engineers using FOCUS-aligned terminology, with honest estimate-vs-realised labelling. Use when the Visualizer builds reports.
---

# FinOps reporting

Two audiences, one truth. Keep basis and confidence on every number.

## Executive summary (`executive-summary.md`)

- Spend trend over the window (total + top services), in AUD / en-AU by default.
- **Estimated** monthly saving opportunity and **Realised** monthly saving — shown as two separate
  totals, never merged.
- Headline findings (3–5), each with tier and confidence.
- Current status: how many proposed / approved / PR-open / merged / verified.

## Engineer backlog (`engineer-backlog.md`)

- Ranked table: id, type, tier, resource, est. saving + basis, confidence, effort, iacMatch, status.
- Group by tier or by type; make each row actionable.

## Savings ledger (`savings-ledger.json`)

- Generate with `python scripts/ledger.py .finops/runs/<id>/`.
- Separates estimated vs realised, by finding type.

## FOCUS-aligned terminology

Use consistent terms: *billed cost*, *effective cost*, *amortized cost*, *list unit price*,
*contracted unit price*, *resource*, *service*, *region*, *tag/allocation*. Prefer these over
ad-hoc labels.

## Honesty rules

- Never present a list-price estimate as realised. Realised comes only from `verification/*.json`
  (`confirmed`/`partial`).
- Attempt `cost.query_spend` (`arm.query_costs`) before assuming it's unavailable. If spend data is
  genuinely unavailable (the call actually failed), state "spend data unavailable: `<reason>`"
  rather than inventing a total or trend. Report the **currency the API actually returned** —
  never silently convert it to match the report's configured default currency.
- Show the price `basis` and `confidence` next to each saving.
