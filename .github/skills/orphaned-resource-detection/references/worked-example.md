# Worked example — orphaned disk evidence

A concrete `findings/waste.json` evidence entry, the shape the Analyser should produce.

```json
{
  "id": "waste-0001",
  "type": "orphaned-disk",
  "tier": "T1",
  "status": "proposed",
  "evidence": [{
    "capability": "resource.inventory",
    "tool": "arm.execute_query",
    "query": "Resources | where type == 'microsoft.compute/disks' | where properties.diskState == 'Unattached'",
    "timeWindow": "2026-09-15T00:00:00Z/2026-10-14T00:00:00Z",
    "observation": "disk-orphan-01 unattached since 2026-07-01 (105 days), 256GB Premium SSD v2, no activity-log attach events in window"
  }],
  "estimatedMonthlySaving": { "amount": 31.10, "currency": "AUD", "basis": "actual" },
  "iacMatch": { "status": "found", "repo": "infra", "path": "modules/disks/dev.bicep" }
}
```

Note the two things that make this a safe T1, not a guess: the **105-day** unattached duration
(not just "currently unattached") and the **activity-log check** confirming no recent attach
events — a disk unattached for 10 minutes mid-maintenance is not evidence of waste.
