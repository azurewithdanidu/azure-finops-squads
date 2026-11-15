# Azure OpenAI token metrics reference

Exact Azure Monitor metric names, aggregation and dimensions for the `azure-openai-tokens` method,
kept here so `SKILL.md` can stay focused on the method. Source:
[Supported metrics — Microsoft.CognitiveServices/accounts](https://learn.microsoft.com/en-us/azure/azure-monitor/reference/supported-metrics/microsoft-cognitiveservices-accounts-metrics),
category **Azure OpenAI - Usage**.

## Metrics

| Metric (REST API name) | Meaning | Unit | Aggregation | Dimensions | Time grain |
|---|---|---|---|---|---|
| `GeneratedTokens` | Tokens generated (output) by the model. | Count | Total (Sum) | `ApiName`, `ModelDeploymentName`, `FeatureName`, `UsageChannel`, `Region`, `ModelVersion`, `ServiceTierRequest`, `ServiceTierResponse` | PT1M |
| `ProcessedPromptTokens` | Prompt tokens processed (input) by the model. | Count | Total (Sum) | same as above | PT1M |
| `TokenTransaction` | Prompt + generated tokens combined ("Processed Inference Tokens"). Use this instead of summing the two above if you only need one number and don't need the input/output split. | Count | Total (Sum) | same as above | PT1M |

All three apply to PTU, PTU-managed and Pay-as-you-go Azure OpenAI deployments. They only exist on
`Microsoft.CognitiveServices/accounts` resources whose `kind` is an OpenAI kind — plain Cognitive
Search, Vision or Speech resources don't expose them at all.

**Aggregation matters:** always request `Total` (Sum) over the window, never `Average` — an
average token count per sample interval is meaningless for a cost-per-1K-tokens calculation, only
the summed total over the whole window is.

## Worked query example

Query both metrics over the same window as `spend.json`, summed (no dimension split needed unless
you want a per-deployment breakdown):

```bash
az monitor metrics list \
  --resource "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account-name>" \
  --metric "GeneratedTokens,ProcessedPromptTokens" \
  --aggregation Total \
  --interval PT1H \
  --start-time 2026-09-01T00:00:00Z \
  --end-time 2026-10-01T00:00:00Z
```

Sum the `total` values across all returned time buckets for each metric to get the window total,
then add `GeneratedTokens` + `ProcessedPromptTokens` (or use `TokenTransaction` directly) for the
denominator `scripts/kpis.py` expects in `inventory.json`:

```json
{
  "usageMetrics": {
    "azureOpenAI": [
      {
        "resourceId": "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account-name>",
        "generatedTokens": 4200000,
        "processedPromptTokens": 1800000,
        "totalTokens": 6000000
      }
    ]
  }
}
```

`scripts/kpis.py`'s `_total_openai_tokens` prefers an explicit `totalTokens` field when present,
otherwise it sums `generatedTokens` + `processedPromptTokens`.

## Pitfalls

- Don't query `Average` or `Maximum` aggregation for these metrics — only `Total` (Sum) over the
  window gives a correct token count.
- Diagnostic Settings export (`DS Export: Yes` for all three metrics) is the more reliable path for
  a full historical window if the Azure Monitor metrics retention (93 days) doesn't cover it —
  note which source was used in the finding/KPI note.
- Multiple Azure OpenAI accounts each need their own metrics query; don't assume one account's
  token count represents the whole subscription's AI spend.
- A resource's `kind` must be confirmed as an OpenAI kind before querying — these metrics silently
  return no data (not an error) for non-OpenAI Cognitive Services accounts, which can look like
  "zero usage" rather than "wrong resource type" if you don't check `kind` first.
