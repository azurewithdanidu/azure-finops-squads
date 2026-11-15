---
name: finops-remediation
description: Prepare approved Azure FinOps Bicep remediation PRs with explicit risk and consent gates. Use when implementing a specific approved cost finding. Do not use for general Bicep authoring or Azure deployment.
---

# FinOps remediation

Load the `finops-squad` skill and follow its entry preflight and binding installed
`references/safety-contract.md` and `references/risk-tiers.md`, even when invoked directly. Never mutate
Azure, deploy, automatically merge or write run-status.md.

Before any work, refuse missing tier or T3, non-approved findings, and `iacMatch.status` not-found.
An unmanaged finding permits a documented manual request only, not a PR. Require explicit human
confirmation for each finding; T2 requires separate confirmation and a draft PR. Never infer
approval from a flag, prior unrelated approval or automated check.

Run bundled `check_remediation.py <absolute-finding-file> --id <finding-id> --confirmed` only after
actual finding-specific confirmation; add `--confirmed-t2` only after separate T2 confirmation.
`REFUSE` blocks, `MANUAL` permits only a documented manual request, `DRAFT` permits only draft PR.
These flags are assertions, not proof of consent; verify human confirmation independently.

For allowed IaC changes: branch `finops/<finding-id>-<short-slug>`, one logical change per PR;
use `bicep-avm-conventions` and, where applicable, the
`budget-and-alert-bicep`, `devtest-shutdown-schedules`
or `storage-tiering-lifecycle` skills. Use host Bicep schema checks if
available. Validate locally without deployment; fix failed pre-PR checks with at most two attempts
total, then stop and report failure. Use `pr-authoring` to prepare a PR body with evidence,
estimated saving and basis, tier, rollback and verification plan. T0/T1 normal PR, T2 draft only.
After opening, record `pr-open` and `prUrl`. Wait for real merge before verification.
