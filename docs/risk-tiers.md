# Risk tiers

Every finding carries a tier. The finding agent (the Analyser, in the relevant mode) sets it, the
orchestrator re-checks it, and the Implementer refuses missing or **T3** tiers. See the
[risk-tier-assessment skill](../.github/skills/risk-tier-assessment/SKILL.md) for worked examples.

| Tier | Meaning | Examples | Implementer behaviour |
|---|---|---|---|
| **T0** | Safe, additive | add budget/alert, add tags, add dev/test shutdown schedule, storage lifecycle (non-delete) | PR opened directly |
| **T1** | Low risk | delete orphaned unattached disk / public IP older than N days with no recent activity | PR opened; body must include evidence **and** a rollback note |
| **T2** | Medium risk | downsize non-production VM/DB, change storage tier, lifecycle delete rules, apply Hybrid Benefit | **Draft** PR, only after explicit user confirmation |
| **T3** | High risk | production compute/data changes, commitment purchases, deletions of stateful resources | **No PR** — recommendation and analysis only |

## Rules

- **Tier up when in doubt.** Production or stateful ⇒ at least T2, usually T3.
- The Implementer **must refuse** any finding whose tier is missing or T3, and any finding whose
  `iacMatch.status` is not `found` (producing a manual change request for `unmanaged`).
- T2 requires explicit user confirmation and is opened as a **draft** PR.
