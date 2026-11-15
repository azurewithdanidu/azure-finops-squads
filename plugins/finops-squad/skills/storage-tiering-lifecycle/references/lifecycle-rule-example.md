# Lifecycle rule example

A JSON lifecycle policy that tiers then expires blob data, scoped to a `logs/` prefix.

```json
{
  "rules": [{
    "name": "cool-then-archive",
    "enabled": true,
    "type": "Lifecycle",
    "definition": {
      "filters": { "blobTypes": ["blockBlob"], "prefixMatch": ["logs/"] },
      "actions": { "baseBlob": {
        "tierToCool": { "daysAfterModificationGreaterThan": 30 },
        "tierToArchive": { "daysAfterModificationGreaterThan": 180 },
        "delete": { "daysAfterModificationGreaterThan": 365 }
      }}
    }
  }]
}
```

`tierToCool`/`tierToArchive` actions are additive (T0). Any rule that also adds a `delete` action
is destructive and irreversible — tier that version of the finding as **T2** and require
confirmation before the Implementer opens even a draft PR.

## Tier guidance (reference)

| Tier | Use when | Trade-off |
|---|---|---|
| Hot | accessed frequently | highest storage, lowest access cost |
| Cool | infrequent, ≥ 30 days | lower storage, higher access + early-deletion fee (30d) |
| Cold | rare, ≥ 90 days | lower still, 90d early-deletion fee |
| Archive | rarely, ≥ 180 days | cheapest storage, rehydration latency + cost |
