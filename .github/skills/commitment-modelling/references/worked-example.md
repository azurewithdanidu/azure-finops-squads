# Worked example — break-even and coverage

## Baseline

6 months of `arm.query_costs` for compute, grouped monthly: $9,200 / $9,050 / $11,400 (spike —
temporary load test) / $9,300 / $9,150 / $9,400. **Committable baseline = $9,050** (the stable
floor), not the $11,400 peak.

## Coverage target

Recommend committing to 70% of the baseline (~$6,335/month) rather than 100%, leaving headroom for
normal variance and avoiding paying for unused commitment if usage dips.

## Break-even (simplified)

```text
break_even_months = commitment_upfront / monthly_saving
```

A 3-year Reserved Instance with $9,600 upfront and a $420/month saving vs pay-as-you-go breaks even
at month 23. That's only worth recommending if the workload is confidently expected to run past
month 23 — state that assumption explicitly in the finding.

## Mix

Savings Plans (flexible across compute, smaller discount) can cover the baseline while a narrower
1-year RI covers a specific, unlikely-to-change instance family — model the mix, not just one
option, before recommending.
