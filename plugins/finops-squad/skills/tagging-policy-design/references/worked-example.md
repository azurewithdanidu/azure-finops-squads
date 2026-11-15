# Worked example — Azure Policy for required tags

A conservative, audit-first rollout before any `deny` is considered.

```json
{
  "mode": "Indexed",
  "policyRule": {
    "if": {
      "allOf": [
        { "field": "type", "notEquals": "Microsoft.Resources/subscriptions/resourceGroups" },
        { "field": "tags['costCenter']", "exists": "false" }
      ]
    },
    "then": {
      "effect": "audit"
    }
  }
}
```

## Rollout sequence

1. **Audit** this definition for 2–4 weeks; measure how many resources/how much spend would be
   non-compliant.
2. Add a companion **modify** policy with `conflictEffect: deny` set to `false` that backfills
   `costCenter` from the resource group's tag via `roleDefinitionIds` with
   `Microsoft.Resources/subscriptions/resourceGroups/write`.
3. Only move the `costCenter` policy to **deny** once coverage is high and teams have had a
   migration window — a hard deny on day one blocks deployments and erodes trust in the squad's
   recommendations.
