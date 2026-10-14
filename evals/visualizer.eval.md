# Eval: finops-visualizer

Checks that reports keep estimated and realised savings strictly separate and label basis/confidence.

## Setup

Run against [`fixtures/`](../fixtures): four findings (estimated total AUD 194.84) and one confirmed
verification (realised AUD 24.58).

## Case 1 — executive summary

**Prompt:** "Write the executive summary for this run."

**Expected:** Shows **estimated** (194.84) and **realised** (24.58) monthly savings as two separate
totals — never merged. Uses AUD / en-AU formatting. Each saving shows basis and confidence.

## Case 2 — savings ledger

**Prompt:** "Build the savings ledger."

**Expected:** Runs `python scripts/ledger.py <run>/`. Ledger `totals.estimatedMonthly = 194.84`,
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

## Case 5 — points to the dashboard

**Prompt:** "I'd like to look at this interactively."

**Expected:** Mentions `streamlit run scripts/dashboard.py` as the companion interactive view,
without treating it as a replacement for the Markdown/JSON reports.

## Pass criteria

- Estimated vs realised always separated.
- Basis + confidence shown on every number.
- Honest handling when spend is unavailable; read-only.
