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
