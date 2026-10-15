# Network appliance false-positive example

Never call a firewall, NAT gateway, or VPN/ExpressRoute gateway idle from a bandwidth metric alone.

## Worked example from a live investigation

An Azure Firewall showed `Throughput` averaging **0 bits/sec** over 7 days (daily grain) — on its
own, that looked like a clean "idle, delete it" candidate, especially since it was also the
subscription's single largest cost line. But a second metric, `NetworkRuleHit`, showed
**~43,000 hits/day, every day** — the firewall was actively evaluating real traffic the whole
time. The `Throughput` average simply rounded down at daily granularity because the traffic was
small-packet/rule-evaluation volume, not bulk data transfer. Concluding "idle" from `Throughput`
alone would have produced a false-positive finding against a production hub resource.

## Rule for this category

Before proposing any finding for a firewall, NAT gateway, VPN gateway, or ExpressRoute gateway,
pull **at least two independent signals** — e.g. `Throughput`/`DataProcessed` **and**
`NetworkRuleHit`/`ApplicationRuleHit`/connection-count — and only conclude idle if **all** of them
are near-zero across the whole window. A high cost alone is never evidence of waste; it only tells
you where to look.
