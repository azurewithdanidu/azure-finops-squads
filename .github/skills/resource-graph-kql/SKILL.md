---
name: resource-graph-kql
description: Write Azure Resource Graph (KQL) queries for inventory, orphan detection and tagging gaps. Use when you need a broad, cross-subscription view of resources and their state.
---

# Resource Graph (KQL) query patterns

**Use `arm.execute_query`** to run KQL across subscriptions — live-verified working in this agent
host. Prefer it over the host tool `azure_query_azure_resource_graph`, which has returned a
"not registered" error in practice; fall back to it (or to `az graph query` via the CLI) only if
`arm.execute_query` is unavailable in your environment. This is the fastest way to inventory
resources and spot orphans without per-resource calls.

## When to use

- Building `inventory.json`.
- Finding orphans (unattached disks, unassociated public IPs, empty NICs).
- Measuring tag coverage.

## Inputs

| Source | Role |
|---|---|
| `arm.generate_query` | Natural language → draft KQL, for a query you're unsure how to write |
| `arm.validate_query` | Syntax check before running, to avoid wasted round-trips |
| `arm.execute_query` | Runs the validated KQL across the scoped subscriptions |

## Outputs

| Artifact / field | Result |
|---|---|
| `inventory.json` | Resource rows with id, type, location, resourceGroup, sku, tags |
| Orphan candidate lists | Feeds `findings/waste.json` evidence (disk/IP/NIC ids + state) |
| Tag coverage counts | Feeds `findings/tagging.json` coverage/allocation numbers |
| `inventory.json` `tagCoverage.fullyTaggedCount` / `resourceGroupTags` | Feeds `scripts/kpis.py`'s `taggingCompliance` and `allocationCoverage` KPIs |

## Method

1. For an unfamiliar query: `arm.generate_query` (natural language → KQL) → `arm.validate_query`
   (syntax check) → `arm.execute_query` (run it).
2. After executing, always check for a `skipToken` in the response and page through with it —
   treat results as non-conclusive until no `skipToken` is returned.
3. Use the tested queries in
   [references/kql-query-catalog.md](references/kql-query-catalog.md) (inventory, unattached
   disks, unassociated public IPs, empty NICs, per-tag coverage, **fully-tagged resource count**,
   **resource group tags**) as your starting point rather than writing each query from scratch.
   The fully-tagged and resource-group-tag queries back the KPI dashboard's tagging-compliance and
   allocation-coverage metrics — prefer them over per-tag counts when building `inventory.json`.

## Pitfalls

- Resource Graph property casing is lowercase for `type`; property paths are case-sensitive.
- Resource Graph is eventually consistent — note the query time in evidence.
- Page large results (`| take`/`$skipToken`); don't assume a single page is complete.
- Resource Graph has **no cost data** — join with spend from `cost.query_spend` separately.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Resource Graph overview | https://learn.microsoft.com/en-us/azure/governance/resource-graph/overview |
| Resource Graph query language (KQL subset) | https://learn.microsoft.com/en-us/azure/governance/resource-graph/concepts/query-language |
| Starter queries and samples | https://learn.microsoft.com/en-us/azure/governance/resource-graph/samples/starter |
| `az graph query` CLI reference | https://learn.microsoft.com/en-us/cli/azure/graph |

### Key takeaways

- `arm.execute_query` is live-verified in this host; `azure_query_azure_resource_graph` is not —
  don't retry the broken tool before falling back to the CLI.
- A result page without a `skipToken` is the only safe "complete" signal — anything else risks an
  undercount in `inventory.json` or a finding.
- Resource Graph tells you *what* and *state*; it never tells you *cost* — pair it with
  [cost-query-patterns](../cost-query-patterns/SKILL.md).
