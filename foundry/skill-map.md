# Foundry skill map

Source of truth is `.github/skills`. Upload with `scripts/sync-skills.ps1`; the toolbox is defined
in `toolbox.yaml` (`finops-skills`, default version 1, project `danidu-agentic-migrations`).

Per-agent skill sets (applied in phase 3 when each hosted agent is created; skills load on demand,
so agents may attach only their own list to keep context small):

| Agent | Skills |
|---|---|
| orchestrator | run-orchestration, phase-delegation, iteration-brief, risk-tier-assessment |
| discovery | resource-graph-kql, cost-query-patterns, advisor-cost-recommendations |
| analyser | idle-compute-detection, orphaned-resource-detection, commitment-modelling, hybrid-benefit-eligibility, storage-tiering-lifecycle, tagging-policy-design, anomaly-explanation, unit-economics, price-basis-handling, savings-verification, risk-tier-assessment |
| implementer | bicep-avm-conventions, iac-matching, pr-authoring, budget-and-alert-bicep, devtest-shutdown-schedules, risk-tier-assessment |
| visualizer | finops-reporting, unit-economics |

Rollback a skill: `azd ai skill update <name> --set-default-version <n>`.
