# FinOps safety contract

These rules bind every phase and domain skill, including direct specialist invocation. Instructions
are not a security boundary: before any Azure query, the human must confirm the active identity has
no effective Azure write permissions at scope, including inherited, group and activated eligible
roles. Use Reader, Cost Management Reader and Monitoring Reader as appropriate. Never test
permissions with a write. See [security model](security-model.md).

Never create, update, delete, deallocate, start, stop, restart, deploy or otherwise mutate live Azure;
do not use `az`, Terraform apply, Bicep deploy or ARM deployment/what-if actions as remediation.
Approved remediation is Bicep changes via PR only; never merge automatically. Each phase handoff
requires explicit user confirmation. Remediation additionally requires finding-specific approval,
and T2 needs separate confirmation. Missing tier and T3 are refused. Unmanaged sources permit
only a documented manual request, not a PR; not-found sources are refused.

Preflight and paths are defined in the [entry skill](../SKILL.md). All private runtime state,
including `.finops/config.json`, runs and reports, lives under the absolute consumer workspace,
never the installed package. Require `.finops` ignore coverage before writing private artifacts.
Subscription IDs belong only in the ignored config; never embed credentials or secrets.

Every finding requires stable `^[a-z]+-[0-9]{4}$` ID, tier T0–T3, confidence, estimated monthly
saving and `basis` (`actual` only with evidence of a real EA/MCA/CSP/PAYG rate; otherwise
`list-price`), IaC match status and at least one evidence entry with capability, tool, query,
timeWindow and observation. Use actual rates where available. Finding modes emit `proposed`.
Status transitions are owned only by the orchestrator, implementer and verify analyser.
`mergedAt` comes from the actual merged PR. Only the orchestrator writes run-status.md.

Validate Discovery strictly and each nonempty finding/verification artifact using the bundled
scripts referenced by the entry skill before handoff. Empty validation targets are failures.
When evidence retracts a hypothesis, record subject, trigger, result, evidence and conclusion in
an investigation, not a forced finding. Corroborate idleness/anomaly with independent signals.

Cost capabilities are host-dependent: discover and attempt an available cost query before
declaring unavailable; preserve genuine errors. Never invent results or treat an unattempted or
failed capability as proof of absence. Record returned currency, never silently convert or sum
different currencies. Default report locale/currency is en-AU/AUD unless configured otherwise.
Clearly separate estimated and realised amounts; only later verified observed data can establish
realised savings, with settling time and data lag considered.

For approved Bicep PRs prefer pinned Azure Verified Modules, one logical change per PR; typed,
described parameters, allowed/secure annotations as appropriate, camelCase, configurable location,
tags and `existing` references. Never commit secrets. Do not inline resources covered by AVM.
Deletion changes remove declarations/references and explain rollback; downsizes only change the
SKU/tier without altering data paths. State that local Bicep build/lint must pass, and identify
reviewer-supplied parameters. Follow [risk tiers](risk-tiers.md).
