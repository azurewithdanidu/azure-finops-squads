---
description: Evaluation scenarios for static FinOps reports.
---

# Eval: finops-visualizer

Checks that reports keep estimated and realised savings strictly separate and label basis/confidence.

## Setup

Run against [`fixtures/`](../fixtures/legacy): four findings (estimated total AUD 194.84) and one confirmed
verification (realised AUD 24.58).

## Case 1 — executive summary

**Prompt:** "Write the executive summary for this run."

**Expected:** Shows **estimated** (194.84) and **realised** (24.58) monthly savings as two separate
totals — never merged. Uses AUD / en-AU formatting. Each saving shows basis and confidence.

## Case 2 — savings ledger

**Prompt:** "Build the savings ledger."

**Expected:** Runs `python -B "../../skills/finops-squad/scripts/ledger.py" <run>/`. Ledger `totals.estimatedMonthly = 194.84`,
`totals.realisedMonthly = 24.58`, with per-type breakdown.

## Case 3 — spend genuinely unavailable

**Prompt:** Run with `spend.json` marked `{"status": "unavailable", "reason": "<a real tool error>"}`.

**Expected:** States "spend data unavailable: `<the recorded reason>`" instead of inventing a total
or trend. Does **not** assume this means a server is permanently disconnected — `arm.query_costs`
is normally available in this host; this status should only appear after Discovery actually
attempted the call and it failed.

## Case 3b — spend available (the common case)

**Prompt:** Run with `spend.json` marked `{"status": "available", ...}` with real `byService` data
and a `currency` field.

**Expected:** Reports the real total and top services, using **the currency the data actually
carries** (e.g. USD) rather than silently converting to the report's configured default currency
(e.g. AUD). If they differ, states both and does not combine them.

## Case 4 — no estimate presented as realised

**Expected:** No list-price estimate appears in the realised column; realised figures come only from
`verification/*.json` with result `confirmed`/`partial`.

## Case 5 — retrospective, only with an iteration brief

**Setup:** Run with an `iteration.md`/`iteration.json` present (goal: resolve 2 orphaned public
IPs; baseline 2 open, target 0) and `findings/waste.json` showing 1 of the 2 now resolved
(compared against the prior run via `resourceId`).

**Prompt:** "Close out this iteration."

**Expected:** Writes `reports/retrospective.md` with: goal progress (baseline 2 → current 1,
target 0 — partial progress, not "done"), realised vs estimated scoped to this iteration's
findings, the still-open finding listed as a blocker (not a failed saving), and 1-2 candidate next
goals grounded in what's still open. **Does not** write a retrospective if no `iteration.json`
exists for this run.

## Case 6 — mixed-currency ledger

**Setup:** `reports/savings-ledger.json` has `"mixedCurrencies": true` with `byCurrency` entries
for both `AUD` and `USD`.

**Prompt:** "What's the total estimated saving for this run?"

**Expected:** Does **not** state a single blended total across currencies. Reports each currency's
total from `byCurrency` separately (e.g. "AUD 29.44/month across 2 findings; USD 92.00/month
across 1 finding") and explains why they aren't combined.

## Case 7 — malformed finding file

**Setup:** One file under `findings/` is malformed JSON (e.g. a truncated file).

**Prompt:** "Build the engineer backlog."

**Expected:** Does not crash or silently drop the whole run's reporting. Reports show a
clear "N file(s) could not be read" note (what and why) alongside valid findings — the same
honesty rule as a genuinely unavailable capability (never silently show less data than actually
exists without saying so).

## Case 8 — named KPI set, generated and honest about gaps

**Setup:** Run with `inventory.json` lacking `resources[]`/`tagCoverage` data, and no `spend.json`
resource-group breakdown.

**Prompt:** "Build the KPI set for this run."

**Expected:** Runs `python -B "../../skills/finops-squad/scripts/kpis.py" <run>/ --runs-dir .finops/runs`. Reports all 5 named
KPIs (`taggingCompliance`, `allocationCoverage`, `estimatedSavingsOpportunity`,
`realisedSavingsRate`, `anomalyCount`) — the two with missing inputs show
`method: "unavailable"` with a specific `note` explaining exactly what's missing, never a guessed
number. `realisedSavingsRate` reports a true `0%` (not "unavailable") when nothing is estimated
yet — a zero and a missing value are not the same thing.

## Pass criteria

- Estimated vs realised always separated.
- Basis + confidence shown on every number.
- Honest handling when spend is unavailable; read-only.
- No currency total ever blends more than one currency.
- A retrospective only appears when an iteration brief exists, and never overstates goal progress.
- Every KPI states its own `method`/`trend` and, when unavailable, exactly why — never a fabricated
  number standing in for missing data.
