# Worked example — delta decomposition

"Spend went up" turned into an auditable explanation.

## Detect

Trailing-4-week average for Compute in `rg-prod` was $1,180/week. Last week was $1,600/week — a
+36% delta, above the 20% threshold.

## Decompose

```text
Compute +$420 (week over week)
  rg-prod/vm-api-03   +$140  (existing D4s_v5, no change)
  rg-prod/vm-api-04   +$140  (new D4s_v5, created 6 days ago)
  rg-prod/vm-api-05   +$140  (new D4s_v5, created 6 days ago)
```

## Correlate

Activity log shows two `Microsoft.Compute/virtualMachines/write` events for `vm-api-04` and
`vm-api-05` timestamped 6 days ago, matching a deployment pipeline run tagged `release-2026.10`.

## Classify

**Expected** — a planned scale-out tied to a known release. Finding is `type: "anomaly"`,
tier `T0` (explanatory), `estimatedMonthlySaving: 0` unless the scale-out itself looks oversized
(in which case, hand off to `rightsizing` mode separately rather than conflating the two).
