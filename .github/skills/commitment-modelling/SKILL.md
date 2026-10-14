---
name: commitment-modelling
description: Model reservations vs savings plans — break-even, coverage and lock-in risk. Use when stable baseline usage suggests a commitment could cut pay-as-you-go cost.
---

# Commitment modelling (reservations vs savings plans)

Commitment **purchases are T3** — produce a recommendation with analysis only, never a PR. Full
modelling needs `commitments.list` + `cost.query_spend` (ARM MCP); if unavailable, model from spend
history + Advisor and lower confidence.

## Concepts

- **Reserved Instances (RI):** biggest discount, narrowest flexibility (instance family/region).
- **Savings Plans:** hourly $ commitment, flexible across compute, usually a smaller discount.
- **Term:** 1y vs 3y — 3y discounts more but increases lock-in risk.

## Method

1. Establish **committable baseline** = the floor of stable usage over the last 3–6 months (not the
   peak). Commit below the baseline to avoid paying for unused commitment.
2. For each option compute: effective discount %, **break-even month**, **coverage %** of eligible
   spend, and flexibility.
3. Recommend a coverage target (commonly 60–80% of the stable baseline) leaving headroom for change.

## Break-even (simplified)

`break_even_months = commitment_upfront / monthly_saving`. A 3y RI that breaks even at month 20 is
only worthwhile if you're confident the workload survives well past month 20.

## Pitfalls

- Don't commit to peak or growing-then-shrinking usage.
- Account for planned migrations/decommissions within the term.
- Savings plans and RIs can be combined; model the mix, not just one.
- Label all figures as **estimates**; realised savings require later cost data.
