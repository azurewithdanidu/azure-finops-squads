---
description: Canonical plugin rules for approval-gated Bicep remediation.
applyTo: "**/*.bicep"
---

# FinOps Bicep changes

Load the packaged `finops-remediation` and `bicep-avm-conventions` skills and the
[safety contract](../../plugins/finops-squad/skills/finops-squad/references/safety-contract.md).
The plugin's skills carry the full runtime rules; consumer repositories do not inherit this
source repository's instructions.

Never deploy or mutate Azure. Require finding-specific approval and an IaC match before editing;
T3 and untiered changes are analysis-only and T2 requires separate confirmation and a draft PR.
Keep one logical change per PR, use pinned AVM modules, preserve evidence and include rollback
and later verification plans.
