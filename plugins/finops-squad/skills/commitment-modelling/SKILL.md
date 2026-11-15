---
name: commitment-modelling
description: Model Azure reservations and savings plans for cost optimisation. Use when a FinOps audit finds stable baseline usage. Do not use to purchase commitments or deploy resources.
---

# Commitment modelling (reservations vs savings plans)

Load the `finops-squad` skill, follow its preflight and its installed `references/safety-contract.md`.

Commitment **purchases are T3** — produce a recommendation with analysis only, never a PR. Full
modelling needs `commitments.list` + `cost.query_spend` (ARM MCP); if unavailable, model from spend
history + Advisor and lower confidence.

## When to use

- Spend history shows stable or growing baseline usage in a compute/database family that might
  benefit from a reservation or savings plan.

## Inputs

| Source | Role |
|---|---|
| `arm.query_costs` (3–6 months) | Establishes the committable baseline |
| `advisor.json` | Secondary source when spend history is sparse |

## Outputs

| Artifact / field | Result |
|---|---|
| `findings/commitments.json` entry (tier `T3`, `iacMatch.status: "unmanaged"`) | Coverage/discount/break-even recommendation, analysis only |

## Concepts

- **Reserved Instances (RI):** biggest discount, narrowest flexibility (instance family/region).
- **Savings Plans:** hourly $ commitment, flexible across compute, usually a smaller discount.
- **Term:** 1y vs 3y — 3y discounts more but increases lock-in risk.

## Method

1. Establish **committable baseline** = the floor of stable usage over the last 3–6 months (not the
   peak). Commit below the baseline to avoid paying for unused commitment.
2. For each option compute: effective discount %, **break-even month**, **coverage %** of eligible
   spend, and flexibility. A full worked example (baseline, coverage target, break-even, mix) is in
   [references/worked-example.md](references/worked-example.md).
3. Recommend a coverage target (commonly 60–80% of the stable baseline) leaving headroom for change.

## Pitfalls

- Don't commit to peak or growing-then-shrinking usage.
- Account for planned migrations/decommissions within the term.
- Savings plans and RIs can be combined; model the mix, not just one.
- Label all figures as **estimates**; realised savings require later cost data.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Reserved Instances overview | <https://learn.microsoft.com/en-us/azure/cost-management-billing/reservations/save-compute-costs-reservations> |
| Azure savings plans for compute | <https://learn.microsoft.com/en-us/azure/cost-management-billing/savings-plan/savings-plan-compute-overview> |
| Reservation vs savings plan decision guide | <https://learn.microsoft.com/en-us/azure/cost-management-billing/savings-plan/decide-between-savings-plan-reservation> |

### Key takeaways

- Commit to the floor, never the peak — a committed spend above actual stable usage is pure waste.
- Break-even month is only meaningful next to a workload-survival estimate — always state the
  assumption alongside the number.
