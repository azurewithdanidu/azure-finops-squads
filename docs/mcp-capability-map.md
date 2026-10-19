# MCP Capability Map (updated 2026-10-14)

Maps each capability from the plan (section 4) to **real** tools, verified by **live calls**
against a real subscription in this session wherever marked "live-verified". Agents reason about
capabilities; this file is the only place that names concrete tools.

Legend: ✅ available (live-verified unless noted) · 🟡 partial · ⛔ **GAP** (no backing tool today)

| Capability | Status | Backend (real tool) | Notes |
|---|---|---|---|
| `inventory.list_resources` | ✅ | `arm` tool: `execute_query` (Resource Graph KQL), `generate_query`, `validate_query` | **Live-verified**: queried unattached disks via KQL against a real subscription. Replaces the host tool `azure_query_azure_resource_graph`, which returned "no implementation registered" in this harness. |
| `cost.query_spend` | ✅ | `arm` tool: `query_costs` | **Live-verified**: pulled real spend by `ServiceName` and by day for a real subscription (see evidence below). Was previously marked GAP — that was wrong; see "Correction" below. |
| `cost.query_aks` | ✅ (schema-verified) | `arm` tool: `query_aks_costs` | Schema confirmed (Cluster/Namespace/UtilizationBucket/ServiceCategory dimensions). Not exercised against real data — no AKS resources in the test subscription. |
| `pricing.retail_lookup` | ✅ | `arm` tool: `get_retail_prices`; also the public Azure Retail Prices REST API (no-auth) | **Live-verified** via both the `arm` tool and the raw REST API (AUD Premium disk / public IP rates). |
| `cost.forecast` | ⛔ | — | The `arm` tool group has no forecast command. Still a GAP. Interim: trend `query_costs` history yourself. |
| `budget.list` | ⛔ | — | The `arm` tool group has no budget command. Still a GAP. |
| `commitments.list` | ⛔ | — | The `arm` tool group has no reservation/savings-plan command. Still a GAP. |
| `advisor.cost_recommendations` | ✅ | `advisor` tool: `advisor_recommendation_list`; `optimization` tool: `recommendation_list` / `explain` / `alternatives` | **Live-verified**: 8 real recommendations returned (VM/PostgreSQL/App Service/Cosmos DB reserved-instance ideas, a savings-plan idea, and two "(Preview)" idle-gateway/ExpressRoute items). |
| `metrics.utilization` | ✅ | `monitor` tool: `monitor_metrics_query` / `monitor_metrics_batchquery` / `monitor_metrics_definitions`; `monitor_activitylog_list` for anomaly context | **Live-verified**: queried `Throughput`, `NetworkRuleHit`, `ApplicationRuleHit`, `DataProcessed` for a real Azure Firewall over 7 days. |

---

## Correction (2026-10-14): `cost.query_spend` / `cost.query_aks` / `inventory.list_resources` are NOT gaps

An earlier revision of this document marked these as GAP/partial, blocked on "the ARM MCP
(CostManagement) server — endpoint unverified" (a separate HTTP server, speculative URL
`https://mcp.management.azure.com`, from the original plan). That framing was wrong.

**What's actually true:** in this agent-host environment (GitHub Copilot in VS Code), there is an
`arm` tool command group — alongside `compute`, `storage`, `monitor`, `advisor`, `optimization`,
`pricing`, etc. — that already provides Cost Management querying (`query_costs`,
`query_aks_costs`), Resource Graph (`execute_query`, `generate_query`, `validate_query`), and retail
pricing (`get_retail_prices`), **with no extra server config, header, or toolset flag required.**
It worked immediately. No separate HTTP endpoint needs verifying.

**Important caveat — where `arm` actually comes from.** The `arm` command group is **not** part of
the standalone `@azure/mcp` npm package configured in `.vscode/mcp.json` (confirmed: `@azure/mcp`
latest is still `3.0.0`, and its own `tools list` enumerates 404 tools across ~65 namespaces with
**no `arm` namespace**). The `arm` tools observed live in this session come from this specific
agent host's own built-in Azure integration, not from the npm server we installed. Practically:

- **Inside GitHub Copilot / VS Code agent sessions** (the actual target environment for
  finops-squad), agents can call `arm` directly — it is available without any `.vscode/mcp.json`
  change.
- **Portability is not guaranteed.** A different host, or the standalone `@azure/mcp` CLI alone,
  may not expose `arm`. Agents should attempt `arm.query_costs` first and only fall back to
  "spend data unavailable" if the call genuinely fails in that environment (see
  [cost-query-patterns](../.github/skills/cost-query-patterns/SKILL.md)).
- `.vscode/mcp.json`'s `azure-resource-manager-mcp` entry (the speculative HTTP endpoint) is no
  longer needed for v0.1 functionality and has been removed from the active config; see
  `.vscode/mcp.json.example` for the updated, honest note.

### Live evidence captured this session

- `query_costs` (scope=subscription, timeframe=TheLastMonth, groupBy=ServiceName, metric=Cost):
  returned 20 services with real USD figures — Azure Firewall $606.85, ExpressRoute $261.87,
  Storage $258.75, API Management $235.89, Azure DNS $189.65, Virtual Machines $181.70, etc.
- `query_costs` (filterDimension=ServiceName, filterValues=Azure Firewall, granularity=Daily):
  returned a daily cost trend (~$42/day on billed days) confirming the backend returns genuine
  time-series cost data, not placeholders.
- `execute_query` (Resource Graph KQL) returned the same 4 real disks as the earlier Azure CLI
  `az graph` fallback — confirming `execute_query` is a correct, working replacement for the
  broken host tool.
- `monitor_metrics_query` returned real daily time series for `NetworkRuleHit` (~43,000/day) and
  `Throughput` (0 avg bps/day) on a production Azure Firewall — see the note on
  [idle-compute-detection](../.github/skills/idle-compute-detection/SKILL.md) about not trusting a
  single metric; this pairing nearly produced a false "idle firewall" finding until corroborated.

---

## Foundry-hosted agents (checked 2026-10-19)

Hosted agents will not have this host's built-in `arm` tool. Direct ARM REST calls with a bearer
token for `https://management.azure.com` work and are the planned replacement (the hosted agent's
managed identity supplies the token):

| Capability | Foundry-host replacement | Check |
|---|---|---|
| `cost.query_spend` | `POST /subscriptions/{id}/providers/Microsoft.CostManagement/query?api-version=2023-11-01` | Live-verified (17 rows, month-to-date by ServiceName) |
| `inventory.list_resources` | `POST /providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01` | Live-verified |
| `pricing.retail_lookup` | Public Retail Prices API (no auth) | Previously verified |
| `advisor`, `metrics.utilization` | ARM REST (Advisor recommendations, Monitor metrics) | Not yet verified from a hosted agent |

## Remaining gaps and follow-up decisions

| Gap | Impact | Recommended resolution |
|---|---|---|
| `cost.forecast` ⛔ | No forecasting tool found anywhere yet | Trend `query_costs` history manually, or keep watching for a forecast command in `arm`. |
| `budget.list` ⛔ | No budget tool found anywhere yet | `missing-budget` findings rely on absence-of-evidence (no budget tool to list existing ones) rather than a positive "0 budgets" query. Document this limitation in the finding's evidence. |
| `commitments.list` ⛔ | Commitment Planner has no live data source | Gate the commitment-planner agent on this; model only from Advisor + `query_costs` trend history in the meantime. |
| `arm` tool portability unverified | Agents calling `arm` outside this specific host may get a tool-not-found error | Always have Discovery try `arm.query_costs` first, catch failure, and only then fall back to the "unavailable" path. |

## What works today

- **Discovery/inventory:** `arm.execute_query` (Resource Graph KQL) + `group_list` /
  `group_resource_list` / `compute` / `storage` / `subscription_list` for detail.
- **Spend:** `arm.query_costs` — by service, resource group, resource, or meter; daily or monthly
  grain; `Cost`, `CostUSD`, or `AmortizedCost` metrics. Max 5 `groupBy` dimensions, no tag grouping,
  ~92-day rolling lookback cap, max 5000 rows.
- **Waste detection:** `compute` (VM power state, disks) + `monitor` metrics, plus Resource Graph
  queries for orphans.
- **Advisor/right-size:** `advisor` + `optimization`.
- **Utilization:** `monitor` metrics — but corroborate with more than one metric before concluding
  idle (see the Azure Firewall example above).
- **Pricing basis:** `arm.get_retail_prices` and the Azure Retail Prices REST API.

**Still not available anywhere:** budgets, forecast, and commitment/reservation listing. The
Visualizer must still label any run missing these as unavailable rather than inventing numbers.
