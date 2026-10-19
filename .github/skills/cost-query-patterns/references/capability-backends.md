# Capability backends

Agents reason about capabilities; the backend differs by host. Always attempt the call first and
only report data as unavailable if it genuinely fails.

| Capability | GitHub Copilot / VS Code host | Foundry-hosted agent |
|---|---|---|
| `cost.query_spend` | `arm` tool `query_costs` | `POST https://management.azure.com/subscriptions/{id}/providers/Microsoft.CostManagement/query?api-version=2023-11-01` |
| `inventory.list_resources` | `arm` tool `execute_query` | `POST https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01` |
| `pricing.retail_lookup` | `arm` tool `get_retail_prices` | Public Retail Prices API (no auth) |
| `advisor.cost_recommendations` | `advisor` / `optimization` tools | ARM REST, Advisor recommendations |
| `metrics.utilization` | `monitor` tools | ARM REST, Monitor metrics |

Not available in either host: `cost.forecast`, `budget.list`, `commitments.list`. Label these
as unavailable; never invent numbers.

Cost query limits: max 5 `groupBy` dimensions, no tag grouping, about 92-day lookback,
max 5000 rows.
