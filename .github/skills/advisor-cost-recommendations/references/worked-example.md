# Worked example — Advisor recommendation to finding

## Sample Advisor recommendation (shape, not a real API response)

```json
{
  "category": "Cost",
  "impact": "Medium",
  "shortDescription": "Right-size or shut down underutilized virtual machines",
  "resourceId": "/subscriptions/<id>/resourceGroups/rg-dev/providers/Microsoft.Compute/virtualMachines/vm-idle-01",
  "extendedProperties": {
    "annualSavingsAmount": "612.40",
    "savingsCurrency": "USD",
    "targetSku": "Standard_D2s_v5"
  }
}
```

## Turning it into evidence, not a copied number

1. Pull the specific resource and validate against **real utilization** over your own window —
   see [idle-compute-detection](../idle-compute-detection/SKILL.md). Advisor's observation window
   is not yours; don't inherit it.
2. Re-price current vs `targetSku` with `pricing`/`arm.get_retail_prices` — see
   [price-basis-handling](../price-basis-handling/SKILL.md) — rather than trusting
   `annualSavingsAmount` verbatim (note it's annual and in `savingsCurrency`, which may not match
   your reporting currency).
3. Only once validated, write the `rightsizing` finding with your own evidence plus a reference to
   the originating Advisor recommendation id/description.
