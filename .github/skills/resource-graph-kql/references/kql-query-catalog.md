# KQL query catalog

Concrete, tested Resource Graph queries for the scenarios `resource-graph-kql` is loaded for.
Adapt field projections as needed; don't change the `where`/`type` filters without re-verifying
against current Resource Graph schema.

## Inventory with key fields

```kql
Resources
| project id, name, type, location, resourceGroup, subscriptionId, sku=properties.sku, tags
| order by type asc
```

## Unattached managed disks

```kql
Resources
| where type == 'microsoft.compute/disks'
| where properties.diskState == 'Unattached'
| project id, name, resourceGroup, location, sizeGb=properties.diskSizeGB, sku=sku.name
```

## Unassociated public IPs

```kql
Resources
| where type == 'microsoft.network/publicipaddresses'
| where isnull(properties.ipConfiguration) and isnull(properties.natGateway)
| project id, name, resourceGroup, location, sku=sku.name
```

## Empty NICs (no VM)

```kql
Resources
| where type == 'microsoft.network/networkinterfaces'
| where isnull(properties.virtualMachine)
| project id, name, resourceGroup, location
```

## Tag coverage gap (missing required tags)

```kql
Resources
| extend hasOwner = isnotempty(tags['owner']), hasCostCenter = isnotempty(tags['costCenter'])
| summarize total=count(), missingOwner=countif(not(hasOwner)), missingCostCenter=countif(not(hasCostCenter)) by type
```

## Fully-tagged resource count (for the Framework's "Overall Tagging Compliance" KPI)

Per-tag missing counts understate non-compliance — a resource missing only one of several
required tags is still non-compliant overall. This query counts resources that carry **every**
required tag, which is what the 90% target in
[tagging-policy-design](../../tagging-policy-design/SKILL.md) actually measures:

```kql
Resources
| extend hasOwner = isnotempty(tags['owner']),
         hasEnvironment = isnotempty(tags['environment']),
         hasApplication = isnotempty(tags['application'])
| extend fullyTagged = hasOwner and hasEnvironment and hasApplication
| summarize total=count(), fullyTaggedCount=countif(fullyTagged)
```

Adjust the `has*`/`fullyTagged` fields to match the org's actual required-tag set (see
`.finops/config.json`'s optional `tagging.requiredTags`, default `owner`/`environment`/`application`
— `scripts/kpis.py` uses the same default list).

## Resource group tags (for allocation-coverage joins)

Resource groups often carry the canonical ownership/cost-centre tags that resources inherit. This
returns every resource group's own tags, suitable for joining against `spend.byResourceGroup` to
estimate what share of spend is allocatable (see `scripts/kpis.py`'s `allocationCoverage` KPI):

```kql
ResourceContainers
| where type == 'microsoft.resources/subscriptions/resourcegroups'
| project name, tags
```

Page with `$skipToken` as usual — a subscription with many resource groups will exceed a single
page.
