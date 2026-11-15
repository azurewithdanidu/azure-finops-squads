---
name: unit-economics
description: Relate Azure FinOps spend to a measured business or technical denominator. Use when analysing cost per token, user or transaction. Do not use for unsupported ROI claims.
---

# Unit economics

Load the `finops-squad` skill, follow its preflight and its installed `references/safety-contract.md`.

A flat spend total doesn't say whether cost is growing because a workload is inefficient or
because it's simply doing more business. Unit economics divides cost by a denominator — tokens,
users, transactions, GB stored — to answer "are we getting more efficient over time?" Never invent
a denominator; this capability is honestly **unavailable** unless real usage data or a
user-configured denominator exists.

## When to use

- An AI/ML workload's cost scales with usage (Azure OpenAI tokens) and a flat total obscures
  whether unit cost is improving or worsening.
- A product/workload's infra cost is best understood per customer, per transaction, or per
  workload rather than as an absolute number.

## Inputs

| Source | Role |
|---|---|
| Azure Monitor metrics for `Microsoft.CognitiveServices/accounts` (Azure OpenAI only) | Real `GeneratedTokens` + `ProcessedPromptTokens` counts |
| `spend.json` `byService` | Matching AI service cost line for the same window |
| `.finops/config.json` → `unitEconomics.denominator` (optional, user-supplied) | Business denominator (e.g. active users, transactions) when no AI token data applies |

## Outputs

| Artifact / field | Result |
|---|---|
| `inventory.json` → `usageMetrics.azureOpenAI[]` (Discovery, optional) | Captured token counts per Azure OpenAI resource |
| `reports/kpis.json` → `kpis.unitEconomics` (via `scripts/kpis.py`) | Computed cost-per-unit, method used, and an honest note when unavailable |

## Two methods, tried in order — never both silently blended

### 1. `azure-openai-tokens` — real usage metrics

Only applies to confirmed Azure OpenAI deployments (`kind` containing `OpenAI` on a
`Microsoft.CognitiveServices/accounts` resource). Azure Monitor exposes **real, billable-adjacent**
token counts for this resource type — see
[references/azure-openai-token-metrics.md](references/azure-openai-token-metrics.md) for the exact
metric names (`GeneratedTokens`, `ProcessedPromptTokens`) and query shape. This is the single most
defensible unit-economics metric available to the squad because it's measured, not estimated.

1. Confirm the resource is an Azure OpenAI deployment, not plain Cognitive Search/Vision/Speech —
   those don't expose token metrics and a token-based unit cost for them would be meaningless.
2. Query `GeneratedTokens` and `ProcessedPromptTokens` (Total/Sum aggregation) over the same window
   as `spend.json`, and record into `inventory.json`'s `usageMetrics.azureOpenAI[]`.
3. `scripts/kpis.py` divides the matching AI spend line by total tokens × 1000 →
   cost per 1K tokens. It matches the spend line **by service name** (contains "openai"), which is
   an approximation if multiple AI services share one billing line — the computed note says so.

### 2. `manual-denominator` — user-supplied business metric

Covers the Framework's broader definition (cost per transaction/customer/workload) without new
Azure capability. The user adds `unitEconomics.denominator` to `.finops/config.json`:

```json
{ "unitEconomics": { "denominator": { "label": "active users", "value": 12000 } } }
```

`scripts/kpis.py` then reports `spend.json`'s `totalLastMonth` ÷ `value`, labelled
`<currency>/<label>` (e.g. `AUD/active users`). See
[references/manual-denominator-examples.md](references/manual-denominator-examples.md) for more
denominator examples and their caveats.

### Fallback: `unavailable`

If neither a real token capture nor a configured denominator exists, `kpis.unitEconomics.method`
is `"unavailable"` with a note naming exactly what's missing. **Never** fabricate a denominator to
avoid reporting unavailable — a wrong unit-cost number is worse than an honest gap.

## Pitfalls

- Don't label a Cognitive Search/Vision/Speech resource's spend as "cost per token" — those
  services aren't token-metered; only Azure OpenAI deployments are.
- A cost-per-unit number without the time window it covers is meaningless — always pair the two.
- Don't silently blend tokens from multiple unrelated AI deployments with different pricing tiers
  into one average without saying so in the note.
- A manual denominator the user forgot to update after a usage change produces a stale, misleading
  trend — the note says it isn't independently verified; flag this to the user periodically.
- Don't compare `unitEconomics` values across runs with different methods (tokens vs manual
  denominator) as if they were the same metric — check `method` before trending.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Supported metrics — Microsoft.CognitiveServices/accounts (Azure OpenAI Usage category) | <https://learn.microsoft.com/en-us/azure/azure-monitor/reference/supported-metrics/microsoft-cognitiveservices-accounts-metrics> |
| Azure OpenAI monitoring guide | <https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/monitoring> |

### FinOps Foundation

| Topic | Link |
|---|---|
| Unit Economics capability | <https://www.finops.org/framework/capabilities/unit-economics/> |

### See also

- [references/azure-openai-token-metrics.md](references/azure-openai-token-metrics.md) — exact
  metric names, aggregation, and a worked `monitor metrics query` example.
- [references/manual-denominator-examples.md](references/manual-denominator-examples.md) — example
  `.finops/config.json` denominators for non-AI workloads.

### Key takeaways

- Only Azure OpenAI deployments expose token metrics — don't assume any Cognitive Services
  resource qualifies.
- A configured denominator is a user claim, not squad-verified evidence — label it as such.
- Honest "unavailable" beats an invented unit cost every time.
