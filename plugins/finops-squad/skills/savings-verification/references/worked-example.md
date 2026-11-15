---
description: Example of a schema-valid savings verification record.
---

# Worked example — verification record

A `verification/<finding-id>.json` record for a confirmed saving, merged 32 days ago.

```json
{
  "findingId": "waste-0001",
  "mergedAt": "2026-09-12T04:00:00Z",
  "checkedAt": "2026-10-14",
  "baselineMonthly": 31.10,
  "observedMonthly": 0.00,
  "realisedSaving": 31.10,
  "result": "confirmed",
  "notes": "32 days since merge (> 7-day settling period, > 3-day cost-data lag). Resource disk-orphan-01 confirmed deleted via Resource Graph; cost slice for the resource id shows $0 for the full post-merge window."
}
```

The amounts use the finding's currency; no currency conversion is implied.

## Why this passes

- The settling period (≥7 days) and cost-data lag (~3 days) are both satisfied and stated in
  `notes` — not just asserted.
- `observedMonthly` comes from an actual re-query of the cost slice, not an assumption that
  deletion implies zero cost.
- `result: "confirmed"` only because `observedMonthly` is within tolerance of 0 for a deleted
  resource — a partial reduction would be `"partial"`, not `"confirmed"`.
