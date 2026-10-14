---
name: risk-tier-assessment
description: Assign the correct risk tier (T0-T3) to a finding and decide the Implementer's allowed behaviour. Use on every finding before remediation.
---

# Risk tier assessment

Tiers gate remediation. The finding agent (the Analyser, in the relevant mode) sets the tier; the
orchestrator re-checks it; the Implementer refuses missing or T3 tiers.

## Tiers

| Tier | Examples | Implementer behaviour |
|---|---|---|
| **T0: Safe** | add budget/alert, add tags, add dev/test shutdown schedule, storage lifecycle (non-delete) | PR opened directly |
| **T1: Low** | delete orphaned unattached disk / public IP older than N days with no recent activity | PR opened; body must include evidence + rollback note |
| **T2: Medium** | downsize non-production VM/DB, change storage tier, lifecycle delete rules, apply AHB | **Draft** PR, only after explicit user confirmation |
| **T3: High** | anything touching production compute/data, commitment purchases, deletions of stateful resources | **No PR.** Recommendation + analysis only |

## Worked examples

- Unattached dev disk, 90d, in IaC → **T1** (PR with rollback).
- Prod VM at 5% CPU → **T3** (analysis only; production compute).
- Non-prod VM oversized, owner known → **T2** (draft PR, confirm first).
- Subscription has no budget → **T0** (PR directly).
- Reservation purchase recommendation → **T3** (never a PR).

## Rules

- When in doubt, **tier up** (treat as higher risk).
- Production or stateful ⇒ at least T2, usually T3.
- A missing tier is unactionable — the Implementer refuses it.
