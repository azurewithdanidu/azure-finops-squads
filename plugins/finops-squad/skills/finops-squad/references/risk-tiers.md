# Risk tiers

| Tier | Scope | Behaviour |
|---|---|---|
| T0 | Additive budgets, alerts, tags, dev/test schedules, non-delete lifecycle | Approved normal PR |
| T1 | Evidenced orphan deletion | Approved normal PR with rollback |
| T2 | Non-production downsize, tier changes, lifecycle deletion, Hybrid Benefit | Separate confirmation, draft PR |
| T3 | Production compute/data, stateful deletion, commitment purchase | Analysis only, no PR |

Tier up when uncertain; production or stateful changes are at least T2, usually T3. Missing tiers
are refused. Not-found IaC is refused; unmanaged means documented manual request only.
See [risk assessment](../../risk-tier-assessment/SKILL.md) for worked cases.
