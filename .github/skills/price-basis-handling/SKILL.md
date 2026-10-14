---
name: price-basis-handling
description: Label savings estimates with the correct price basis (list vs actual) and compute monthly costs consistently. Use on every finding that carries a saving.
---

# Price basis handling

Every saving must declare a `basis`: `list-price` or `actual`. Never leave it blank, and never
present a list-price estimate as a realised saving.

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

## Pitfalls

- Mixing amortized vs actual across findings — pick one and be consistent.
- Treating list-price as actual for a discounted agreement — overstates savings.
- Forgetting that deallocated VMs still bill for disks and IPs.
