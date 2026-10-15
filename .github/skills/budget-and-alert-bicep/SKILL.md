---
name: budget-and-alert-bicep
description: Author AVM-aligned Bicep for cost budgets and alert rules at subscription or resource-group scope. Use when no budget exists or alerting is missing.
---

# Budget & alert Bicep

A missing budget is a **T0** governance gap — safe to PR directly. Budgets don't save money by
themselves; they create visibility and guardrails. Label `estimatedMonthlySaving` as 0 honestly.

## When to use

- Subscription or resource group with no budget / no cost alerts.

## Inputs

| Source | Role |
|---|---|
| `findings/waste.json` entry with `type: "missing-budget"` | The scope (subscription/RG) needing a budget |
| `.finops/config.json` | Default currency/locale for the amount |

## Outputs

| Artifact / field | Result |
|---|---|
| Bicep PR | A `Microsoft.Consumption/budgets` (or AVM module) resource at the right scope |
| `finding.status` | Moves to `pr-open` once opened |

## Method

- Prefer `avm/res/consumption/budget` or `Microsoft.Consumption/budgets` — see the full snippet in
  [references/budget-bicep-snippet.md](references/budget-bicep-snippet.md).
- Parameterize: `amount`, `timeGrain` (Monthly), `thresholds` (e.g. 50/80/100%), `contactEmails`,
  optional `contactRoles`/`contactGroups`.
- Use `Actual` and `Forecasted` notification types.

## Pitfalls

- `startDate` must be the first of a month and not in the past (per API rules).
- Budget scope matters — subscription vs RG vs management group; match the finding scope.
- Alerts need valid contacts; don't invent emails — parameterize and let the reviewer set them.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Consumption budgets resource reference | https://learn.microsoft.com/en-us/azure/templates/microsoft.consumption/budgets |
| Tutorial: Create and manage budgets | https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets |
| Budget action rules / automation | https://learn.microsoft.com/en-us/azure/cost-management-billing/automate/automate-budget-creation |
| AVM consumption budget module | https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/consumption/budget |

### Key takeaways

- A budget is governance, not savings — always label its `estimatedMonthlySaving` as 0 and say why.
- `startDate` rejection (not-first-of-month, in the past) is the most common Bicep validation
  failure for this pattern — set it explicitly rather than relying on a default.
