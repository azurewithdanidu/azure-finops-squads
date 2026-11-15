---
name: finops-discovery
description: Inventory Azure resources, spend and Advisor recommendations for a FinOps audit. Use when collecting discovery evidence for a scoped run. Do not use for deployment or general inventory management.
---

# FinOps discovery

Load the `finops-squad` skill and follow its entry preflight and binding installed
`references/safety-contract.md`, even when invoked directly.
Require explicit read-only RBAC confirmation before Azure. Discover host capabilities using the
`references/capability-map.md` in the installed `finops-squad` skill; do not assume any is installed.
Never write run-status.md.

Input: consumer `.finops/config.json`, absolute run path and confirmed scope/window. Write:

1. `inventory.json`: Resource Graph resource id, type, name, location, group, SKU, state and tags,
   paging all results. Use the `resource-graph-kql` skill and its KQL catalog.
   Include `tagCoverage.fullyTaggedCount` (unless full `resources[]` permits exact calculation) and
   `resourceGroupTags`; if either genuinely fails, record `enrichmentSkipped` entries with
   `field` (`fullyTaggedCount` or `resourceGroupTags`) and real `reason`. No empty placeholders.
2. `spend.json`: attempt the available Cost Management spend query, e.g. `arm.query_costs`, for
   service, resource group and daily totals. Use `cost-query-patterns`
   for top-10-plus-Other daily series, complete daily totals, reconciliation, truncation,
   provisional days and failure handling. A genuine unavailable capability/call failure is
   recorded with its real reason; never fabricate. A daily-only failure is recorded as
   `inventory.json` `enrichmentSkipped` field `daily`.
3. `advisor.json`: collect and validate recommendations using
   `advisor-cost-recommendations`.

Respect rate limits/backoff, pagination, query scope and tool-specific lookback, group and row
limits. Cache within a run. Record API-returned currency and actual/list price basis, never convert
or combine currencies. Validate with bundled `validate_discovery.py <absolute-run> --strict` as
explained in the entry skill. Fix errors; explain every remaining enrichment warning. Hand off
artifact paths and blockers only after inspection; no malformed output.
