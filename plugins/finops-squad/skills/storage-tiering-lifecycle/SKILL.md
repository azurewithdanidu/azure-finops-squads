---
name: storage-tiering-lifecycle
description: Assess storage tiering and lifecycle options for Azure FinOps savings. Use when evidence supports a cost finding. Do not use for generic Bicep writing or live storage changes.
---

# Storage tiering & lifecycle

Load the `finops-squad` skill, follow its preflight and its installed `references/safety-contract.md`.

Match blob access tier to access frequency and automate transitions with lifecycle rules. Tiering
and lifecycle rules are usually **T0–T2** (additive rule vs changing an account's default tier).

## When to use

- Storage spend is high and some data is clearly infrequently accessed (logs, backups, processed
  artifacts) but still sitting in Hot.

## Inputs

| Source | Role |
|---|---|
| Blob metrics / last-modified timestamps | Evidence of actual access pattern, not guesswork |
| `spend.json` storage breakdown | Confirms the scale of the opportunity |

## Outputs

| Artifact / field | Result |
|---|---|
| `findings/waste.json` entry (`type: "storage-tiering"`) | Proposed lifecycle rule + tier, priced |
| Bicep/JSON lifecycle policy (Implementer) | The actual rule added to the storage account |

## Method

1. Inspect blob access patterns / last-modified (use metrics or inventory). Don't tier data that is
   actively read — access charges can exceed storage savings.
2. Prefer a **lifecycle management rule** over bulk-changing the account default tier. A concrete
   example is in [references/lifecycle-rule-example.md](references/lifecycle-rule-example.md),
   along with the tier/trade-off table.
3. Account for **early-deletion fees** and archive **rehydration** cost/latency.

## Pitfalls

- Early-deletion fees make cool/cold worse for data that changes often.
- Archive is offline — not for anything needing quick reads.
- Deleting via lifecycle is irreversible; make `delete` rules T2 and confirm retention policy.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Hot, cool, and archive access tiers | <https://learn.microsoft.com/en-us/azure/storage/blobs/access-tiers-overview> |
| Lifecycle management policies | <https://learn.microsoft.com/en-us/azure/storage/blobs/lifecycle-management-overview> |
| Early deletion / rehydration pricing | <https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-rehydration> |

### Key takeaways

- Tier from measured access patterns, never from a guess — the early-deletion fee can erase the
  saving on data that's cooler on paper but still touched often.
- `tierToCool`/`tierToArchive` is T0; adding `delete` to the same rule turns the whole finding T2.
