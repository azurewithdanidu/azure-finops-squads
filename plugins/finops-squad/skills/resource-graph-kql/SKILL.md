---
name: resource-graph-kql
description: Query Azure Resource Graph for FinOps inventory, orphan and tag evidence. Use when auditing scoped Azure resources. Do not use for generic KQL work or resource mutations.
---

# Resource Graph (KQL) query patterns

Load the `finops-squad` skill, follow its preflight and its installed `references/safety-contract.md`.

Discover a read-only Resource Graph capability in this host, such as `arm.execute_query`, to run
KQL across subscriptions. Availability is host-dependent; if absent record a capability gap rather
than assuming a tool exists or inventing inventory.

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
   The fully-tagged and resource-group-tag queries back the tagging-compliance and
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
| Resource Graph overview | <https://learn.microsoft.com/en-us/azure/governance/resource-graph/overview> |
| Resource Graph query language (KQL subset) | <https://learn.microsoft.com/en-us/azure/governance/resource-graph/concepts/query-language> |
| Starter queries and samples | <https://learn.microsoft.com/en-us/azure/governance/resource-graph/samples/starter> |
| `az graph query` CLI reference | <https://learn.microsoft.com/en-us/cli/azure/graph> |

### Key takeaways

- Resource Graph tool availability varies by host; discover and record capability gaps.
- A result page without a `skipToken` is the only safe "complete" signal — anything else risks an
  undercount in `inventory.json` or a finding.
- Resource Graph tells you *what* and *state*; it never tells you *cost* — pair it with
  `cost-query-patterns`.
