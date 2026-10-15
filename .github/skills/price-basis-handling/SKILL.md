---
name: price-basis-handling
description: Label savings estimates with the correct price basis (list vs actual) and compute monthly costs consistently. Use on every finding that carries a saving.
---

# Price basis handling

Every saving must declare a `basis`: `list-price` or `actual`. Never leave it blank, and never
present a list-price estimate as a realised saving.

## When to use

- Every finding that carries a non-zero `estimatedMonthlySaving`.

## Inputs

| Source | Role |
|---|---|
| `pricing`/`arm.get_retail_prices` | Retail rate for the SKU/region |
| `arm.query_costs` (effective/negotiated rate, where exposed) | Actual rate for EA/MCA/CSP agreements |
| `.finops/config.json` | Report currency default, for conversion/labelling |

## Outputs

| Artifact / field | Result |
|---|---|
| `finding.estimatedMonthlySaving.basis` | `list-price` or `actual`, always set |
| `finding.estimatedMonthlySaving.amount` | Computed consistently per the method below |

## Project decision (v0.1)

**Require actual rates (EA/MCA/CSP) where available.** For pay-as-you-go subscriptions, the retail
rate *is* the actual rate, so `pricing` retail lookups count as `actual` for PAYG. For EA/MCA/CSP,
use negotiated/effective rates when the cost data exposes them; otherwise fall back to `list-price`
and say so with lower confidence.

## How to decide the basis

| Situation | basis |
|---|---|
| PAYG subscription, retail rate from `pricing` | `actual` |
| EA/MCA/CSP effective rate available in cost data | `actual` |
| Only retail price available for a discounted agreement | `list-price` |
| Advisor's headline saving (retail-based) | `list-price` until re-priced |

## Computing a monthly cost

- Disks: `sizeGB × per-GB-month rate(SKU, region)` (+ transaction cost if relevant).
- Public IP: hourly rate × 730.
- VM: hourly rate(SKU, region) × running hours (not always 730 — schedules reduce this).
- Convert to the config currency (default AUD). State the FX basis if converting.
- Worked numeric examples (disk, public IP, VM downsize) are in
  [references/worked-example.md](references/worked-example.md).

## Pitfalls

- Mixing amortized vs actual across findings — pick one and be consistent.
- Treating list-price as actual for a discounted agreement — overstates savings.
- Forgetting that deallocated VMs still bill for disks and IPs.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Azure Retail Prices API | https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices |
| Understand your Azure bill (EA/MCA rates) | https://learn.microsoft.com/en-us/azure/cost-management-billing/understand/understand-azure-marketplace-charges |
| Pay-as-you-go pricing | https://azure.microsoft.com/en-us/pricing/ |

### Key takeaways

- Never compare a retail-rate current cost against an effective-rate target cost — re-price both
  sides on the same basis before computing a saving.
- `basis` is not a formality — it's the difference between an honest estimate and an overstated one.
