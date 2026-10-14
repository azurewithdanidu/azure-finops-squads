---
name: savings-verification
description: Confirm whether a merged change actually reduced cost, allowing for settling time and cost-data lag. Use after a remediation PR merges.
---

# Savings verification

Close the loop honestly: a saving is only **realised** when later cost data shows it.

## Preconditions

- Finding `status == merged` with a `mergedAt` date.
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
   ([schema](../../../schemas/verification.schema.json)) with `notes` stating the lag allowance.

## Pitfalls

- Deleting then recreating a resource looks like "no saving" — check it stayed gone.
- Seasonal/price changes can mask or mimic savings; compare like-for-like windows.
- Never upgrade a finding to `verified` on an estimate alone.
