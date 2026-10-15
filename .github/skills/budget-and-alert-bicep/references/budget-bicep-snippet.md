# Budget + alert Bicep snippet

AVM-aligned starting point for a subscription or resource-group budget with actual and forecast
notifications.

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

Parameterize: `amount`, `timeGrain` (Monthly), `thresholds` (e.g. 50/80/100%), `contactEmails`,
optional `contactRoles`/`contactGroups`. Prefer `avm/res/consumption/budget` over the raw resource
type where the AVM module is already pinned in the repo.
