---
description: Bicep and Azure Verified Modules (AVM) conventions for remediation PRs.
applyTo: "**/*.bicep"
---

# Bicep / AVM authoring rules (finops-squad Implementer)

These rules apply whenever an agent authors or edits Bicep for a remediation PR. The Implementer
produces Bicep changes only; it never deploys them.

## Modules

- **Prefer Azure Verified Modules (AVM).** Reference registry modules, e.g.
  `br/public:avm/res/<service>/<resource>:<version>`, and pin an explicit version.
- Do not inline resources that an AVM module already covers (budgets, storage, disks, VMs).
- One logical change per PR. Do not refactor unrelated modules in the same change.

## Style

- Use `param` with explicit types and `@description()` decorators for every parameter.
- Use `@allowed()` for constrained values; mark secrets with `@secure()` (but never commit secrets).
- camelCase for parameters/variables; descriptive resource symbolic names.
- Prefer `resourceGroup().location` or a `location` param over hard-coded regions.
- Add `tags` to every resource that supports them; flow a `tags` object param through.
- Use `existing` references instead of re-declaring resources you only need to read.

## Safety for FinOps changes

- **Deletions** (orphaned disk, unassociated public IP): remove the resource declaration and any
  references; include a rollback note in the PR body (how to recreate). T1 and above.
- **Downsizes** (VM SKU, storage tier): change only the SKU/tier parameter; never alter data-path
  settings. These are T2 — draft PR, user confirmation required.
- **Shutdown schedules / budgets / lifecycle rules**: additive, T0 — safe to open directly.
- Never author changes to production stateful resources (T3). Produce analysis only.

## Validation the author should mention

- State that `bicep build` / `az bicep lint` should pass (the Implementer does not run deployments).
- Note any parameters the reviewer must set (e.g. budget threshold, contact emails).
