---
name: bicep-avm-conventions
description: Apply Azure Verified Modules (AVM) and Bicep style when authoring remediation changes. Use whenever the Implementer writes or edits Bicep.
---

# Bicep / AVM conventions

Mirrors [bicep.instructions.md](../../instructions/bicep.instructions.md); use this when actively
authoring a fix.

## Modules

- Prefer AVM registry modules, pinned to a version:
  `module budget 'br/public:avm/res/consumption/budget:<version>' = { ... }`.
- Don't reinvent a resource AVM already wraps. One logical change per PR.

## Parameters & style

- Every `param` typed with an `@description()`; constrain with `@allowed()` where sensible.
- `@secure()` for secrets — but never commit secret values.
- camelCase names; `location` defaults to `resourceGroup().location`.
- Flow a `tags` object through and apply to taggable resources.
- Use `existing` for read-only references.

## FinOps change patterns

| Finding | Change | Tier |
|---|---|---|
| orphaned-disk / orphaned-public-ip | remove declaration + references; add rollback note | T1 |
| missing-budget | add budget module | T0 |
| missing-shutdown-schedule | add DevTestLab schedule | T0 |
| storage-tiering | add lifecycle rule (delete rules → T2) | T0–T2 |
| rightsizing (non-prod) | change SKU param only | T2 (draft PR) |
| anything prod/stateful | none — analysis only | T3 |

## Validation to mention (not run)

- `bicep build` / `az bicep lint` should pass.
- Call out parameters the reviewer must set (thresholds, emails, target SKU).
- The Implementer never deploys; it only proposes.
