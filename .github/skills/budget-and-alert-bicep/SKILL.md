---
name: budget-and-alert-bicep
description: Author AVM-aligned Bicep for cost budgets and alert rules at subscription or resource-group scope. Use when no budget exists or alerting is missing.
---

# Budget & alert Bicep

A missing budget is a **T0** governance gap — safe to PR directly. Budgets don't save money by
themselves; they create visibility and guardrails. Label `estimatedMonthlySaving` as 0 honestly.

## When to use

- Subscription or resource group with no budget / no cost alerts.

## Bicep approach (AVM-aligned)

- Prefer `avm/res/consumption/budget` or `Microsoft.Consumption/budgets`.
- Parameterize: `amount`, `timeGrain` (Monthly), `thresholds` (e.g. 50/80/100%), `contactEmails`,
  optional `contactRoles`/`contactGroups`.
- Use `Actual` and `Forecasted` notification types.

```bicep
resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: budgetName
  properties: {
    category: 'Cost'
    amount: amount
    timeGrain: 'Monthly'
    timePeriod: { startDate: startDate }
    notifications: {
      actual80: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: contactEmails
      }
      forecast100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: contactEmails
      }
    }
  }
}
```

## Pitfalls

- `startDate` must be the first of a month and not in the past (per API rules).
- Budget scope matters — subscription vs RG vs management group; match the finding scope.
- Alerts need valid contacts; don't invent emails — parameterize and let the reviewer set them.
