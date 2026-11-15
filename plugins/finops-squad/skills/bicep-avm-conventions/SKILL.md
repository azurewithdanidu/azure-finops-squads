---
name: bicep-avm-conventions
description: Apply AVM and Bicep conventions to approved Azure FinOps remediation PRs. Use when implementing an approved cost finding. Do not use for general Bicep authoring or AVM review.
---

# Bicep / AVM conventions

Load the `finops-squad` skill, follow its preflight and its installed `references/safety-contract.md`.

Follows that safety contract; use this when actively
authoring a fix.

## When to use

- Every time the Implementer writes or edits a `.bicep`/`.bicepparam` file for a finding.

## Inputs

| Source | Role |
|---|---|
| `bicepschema` | Confirms real resource/module shapes and required parameters |
| `iac-matching` skill result | The exact file/module to edit |

## Outputs

| Artifact / field | Result |
|---|---|
| Bicep diff in the PR | One logical change, AVM-aligned, typed/described parameters |

## Modules

- Prefer AVM registry modules, pinned to a version:
  `module budget 'br/public:avm/res/consumption/budget:<version>' = { ... }`. A full worked example
  is in [references/worked-example.md](references/worked-example.md).
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

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Azure Verified Modules | <https://azure.github.io/Azure-Verified-Modules/> |
| AVM Bicep resource module index | <https://azure.github.io/Azure-Verified-Modules/indexes/bicep/bicep-resource-modules/> |
| Bicep best practices | <https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/best-practices> |
| `bicep lint` | <https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/linter> |

### Key takeaways

- Always pin an exact AVM module version — `:latest` or an untagged reference is not reproducible
  and not reviewable.
- One logical change per PR is non-negotiable even when a finding touches multiple small params —
  split if it isn't genuinely one change.
