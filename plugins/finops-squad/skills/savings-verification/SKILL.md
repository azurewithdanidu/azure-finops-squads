---
name: savings-verification
description: Verify observed Azure FinOps savings after a merged remediation and settling period. Use when cost data is ready to compare with a baseline. Do not use to infer savings from approval alone.
---

# Savings verification

Load the `finops-squad` skill, follow its preflight and its installed `references/safety-contract.md`.

Close the loop honestly: a saving is only **realised** when later cost data shows it.

## When to use

- The Analyser is invoked in `verify` mode for a finding whose `status` is `merged`.

## Inputs

| Source | Role |
|---|---|
| Finding's `status == merged` + `mergedAt` | Confirms the precondition and the settling-period clock |
| `arm.query_costs` (post-merge window) | The observed cost slice to compare against baseline |

## Outputs

| Artifact / field | Result |
|---|---|
| `verification/<finding-id>.json` | `result`, `realisedSaving`, `notes` — see schema and worked example below |
| `finding.status` | Moves to `verified` only on a `confirmed` result |

## Preconditions

- Finding `status == merged` with `mergedAt` taken from the merged PR, as a UTC date or
  timestamp. Do not infer the merge time from the approval or PR creation date.
- A **settling period** has elapsed: default ≥ **7 days** after merge.
- Allowance for **cost-data lag** (recent days settle for up to ~3 days).

If data is too fresh or lagging, return `result: "inconclusive"` — do not force a verdict.

## Method

1. Re-query the affected resource(s) and the matching cost slice for a window comparable to the
   baseline window.
2. Compute `observedMonthly` and `realisedSaving = baselineMonthly − observedMonthly`.
3. Classify into one of the following results:

   | result | condition |
   |---|---|
   | `confirmed` | observed saving ≈ baseline (within tolerance, e.g. ±10%) |
   | `partial` | 0 < saving < estimate |
   | `not-observed` | no saving despite settled data |
   | `inconclusive` | data too fresh / ambiguous / resource re-created |

4. Write `verification/<finding-id>.json`
   (schema: `schemas/verification.schema.json` in the installed `finops-squad` skill) with `notes` stating the lag allowance. A
   full worked example is in [references/worked-example.md](references/worked-example.md). For an
   inconclusive result, use `null` for any unavailable monthly amounts and explain the missing
   data in `notes`; never use a fabricated zero.

## Pitfalls

- Deleting then recreating a resource looks like "no saving" — check it stayed gone.
- Seasonal/price changes can mask or mimic savings; compare like-for-like windows.
- Never upgrade a finding to `verified` on an estimate alone.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Cost Management data latency | <https://learn.microsoft.com/en-us/azure/cost-management-billing/automate/ratelimits-cost-management-api-data-latency> |
| Understand Cost Management data | <https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/understand-cost-mgt-data> |

### Key takeaways

- The settling period and cost-data lag aren't optional — a verdict issued before both have elapsed
  is not honest, it's a guess with a timestamp.
- `inconclusive` is a valid, often correct answer — resist the pressure to force `confirmed` or
  `not-observed` early.
