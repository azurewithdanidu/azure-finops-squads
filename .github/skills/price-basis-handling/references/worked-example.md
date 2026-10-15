# Worked example — computing a monthly cost

## Orphaned disk

256GB Premium SSD v2 in `australiaeast`, retail rate $0.135/GB-month (from `pricing`):

```text
256 GB x $0.135/GB-month = $34.56/month
```

Subscription is PAYG, so the retail rate **is** the actual rate → `basis: "actual"`.

## Unassociated public IP

Standard SKU, `australiaeast`, retail rate $0.0043/hour:

```text
$0.0043/hour x 730 hours = $3.14/month
```

## Non-production VM downsize

Current `Standard_D4s_v5` at $0.246/hour running 24×7; target `Standard_D2s_v5` at $0.123/hour:

```text
Current:  $0.246 x 730 = $179.58/month
Target:   $0.123 x 730 = $89.79/month
Saving:   $89.79/month
```

Because the subscription is EA and the cost data exposes an effective rate 12% below retail for
this SKU family, re-price both sides with the effective rate before finalizing — do not mix a
retail current-cost with an effective target-cost (or vice versa); pick one basis and use it for
both sides of the comparison.
