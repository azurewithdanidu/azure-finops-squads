---
name: risk-tier-assessment
description: Assign the correct risk tier (T0-T3) to a finding and decide the Implementer's allowed behaviour. Use on every finding before remediation.
---

# Risk tier assessment

Tiers gate remediation. The finding agent (the Analyser, in the relevant mode) sets the tier; the
orchestrator re-checks it; the Implementer refuses missing or T3 tiers.

## When to use

- Every finding, at creation (Analyser) and at ranking time (Orchestrator re-check).
- Every finding, immediately before the Implementer acts on it (hard refusal gate).

## Inputs

| Source | Role |
|---|---|
| Finding's resource type, environment tag (`env`), and change shape | Determines the tier band |
| [iac-matching](../iac-matching/SKILL.md) `iacMatch.status` | Combines with tier to decide PR vs manual request vs refusal |

## Outputs

| Artifact / field | Result |
|---|---|
| `finding.tier` | One of `T0`–`T3`, always set — never blank |
| Implementer behaviour | Direct PR / PR+rollback / draft PR after confirmation / refusal |

## Tiers

| Tier | Examples | Implementer behaviour |
|---|---|---|
| **T0: Safe** | add budget/alert, add tags, add dev/test shutdown schedule, storage lifecycle (non-delete) | PR opened directly |
| **T1: Low** | delete orphaned unattached disk / public IP older than N days with no recent activity | PR opened; body must include evidence + rollback note |
| **T2: Medium** | downsize non-production VM/DB, change storage tier, lifecycle delete rules, apply AHB | **Draft** PR, only after explicit user confirmation |
| **T3: High** | anything touching production compute/data, commitment purchases, deletions of stateful resources | **No PR.** Recommendation + analysis only |

## Method

1. Start from the change shape (additive vs destructive vs SKU/config change) and the resource's
   `env` tag/evidence of production use.
2. Apply the tier table above; when a case doesn't fit cleanly, consult
   [references/worked-examples.md](references/worked-examples.md) for a close analogue.
3. **When in doubt, tier up.** Production or stateful ⇒ at least T2, usually T3.
4. A missing tier is unactionable — the Implementer refuses it.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Resource locks (relevant to what's safe to change without confirmation) | https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/lock-resources |
| Azure Policy effects (`audit`/`modify`/`deny`, relevant to T0 governance changes) | https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effects |

### Key takeaways

- Tiering is a judgement call grounded in blast radius, not just resource type — the same change
  shape can be T0 in dev and T3 in prod.
- A missing tier and a T3 tier are both hard stops for the Implementer — there is no partial-trust
  path around either.
