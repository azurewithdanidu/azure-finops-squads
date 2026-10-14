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

Recommended workflow for a query you're unsure about: `arm.generate_query` (natural language →
KQL) → `arm.validate_query` (syntax check) → `arm.execute_query` (run it). After executing, always
check for a `skipToken` in the response and page through with it — treat results as non-conclusive
until no `skipToken` is returned.

## When to use

- Building `inventory.json`.
- Finding orphans (unattached disks, unassociated public IPs, empty NICs).
- Measuring tag coverage.

## Core patterns

Inventory with key fields:

```kql
Resources
| project id, name, type, location, resourceGroup, subscriptionId, sku=properties.sku, tags
| order by type asc
```

Unattached managed disks:

```kql
Resources
| where type == 'microsoft.compute/disks'
| where properties.diskState == 'Unattached'
| project id, name, resourceGroup, location, sizeGb=properties.diskSizeGB, sku=sku.name
```

Unassociated public IPs:

```kql
Resources
| where type == 'microsoft.network/publicipaddresses'
| where isnull(properties.ipConfiguration) and isnull(properties.natGateway)
| project id, name, resourceGroup, location, sku=sku.name
```

Empty NICs (no VM):

```kql
Resources
| where type == 'microsoft.network/networkinterfaces'
| where isnull(properties.virtualMachine)
| project id, name, resourceGroup, location
```

Tag coverage gap (missing required tags):

```kql
Resources
| extend hasOwner = isnotempty(tags['owner']), hasCostCenter = isnotempty(tags['costCenter'])
| summarize total=count(), missingOwner=countif(not(hasOwner)), missingCostCenter=countif(not(hasCostCenter)) by type
```

## Pitfalls

- Resource Graph property casing is lowercase for `type`; property paths are case-sensitive.
- Resource Graph is eventually consistent — note the query time in evidence.
- Page large results (`| take`/`$skipToken`); don't assume a single page is complete.
- Resource Graph has **no cost data** — join with spend from `cost.query_spend` separately.
