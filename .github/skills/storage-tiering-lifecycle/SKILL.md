---
name: storage-tiering-lifecycle
description: Choose storage access tiers and author lifecycle management rules to move or expire blobs. Use when storage spend is high and access patterns allow cooler tiers.
---

# Storage tiering & lifecycle

Match blob access tier to access frequency and automate transitions with lifecycle rules. Tiering
and lifecycle rules are usually **T0–T2** (additive rule vs changing an account's default tier).

## Tier guidance

| Tier | Use when | Trade-off |
|---|---|---|
| Hot | accessed frequently | highest storage, lowest access cost |
| Cool | infrequent, ≥ 30 days | lower storage, higher access + early-deletion fee (30d) |
| Cold | rare, ≥ 90 days | lower still, 90d early-deletion fee |
| Archive | rarely, ≥ 180 days | cheapest storage, rehydration latency + cost |

## Method

1. Inspect blob access patterns / last-modified (use metrics or inventory). Don't tier data that is
   actively read — access charges can exceed storage savings.
2. Prefer a **lifecycle management rule** over bulk-changing the account default tier.
3. Account for **early-deletion fees** and archive **rehydration** cost/latency.

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

## Pitfalls

- Early-deletion fees make cool/cold worse for data that changes often.
- Archive is offline — not for anything needing quick reads.
- Deleting via lifecycle is irreversible; make `delete` rules T2 and confirm retention policy.
