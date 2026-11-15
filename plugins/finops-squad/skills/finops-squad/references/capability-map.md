# Host-dependent capability map

Discover the host's available read-only tools and their argument schemas before use. None of the
following examples is guaranteed by installation; record missing capabilities and real errors.

| Capability | Possible read-only implementation |
|---|---|
| Inventory | Resource Graph KQL, e.g. `arm.execute_query`, plus resource detail |
| Spend | Cost Management query, e.g. `arm.query_costs` |
| Pricing | Azure Retail Prices or `arm.get_retail_prices`; actual agreement rates where available |
| Advisor | Advisor or optimization recommendation listing |
| Utilisation/activity | Monitor metrics and activity log |
| Budget, commitments, forecast | Host-dependent; explicitly report a gap if unavailable |

Attempt the available spend query first; if absent or genuinely unsuccessful, record why as
unavailable. Never claim a missing capability proves a zero or an absence. See
[cost patterns](../../cost-query-patterns/SKILL.md) and
[Resource Graph](../../resource-graph-kql/SKILL.md).
