---
name: finops-analysis
description: Analyse Azure FinOps evidence for waste, rightsizing, tagging, commitments, anomalies or verified savings. Use when investigating a scoped audit mode. Do not use for Azure deployment or generic security review.
---

# FinOps analysis

Load the `finops-squad` skill and follow its entry preflight and binding installed
`references/safety-contract.md`, even when invoked directly.
Confirm no effective Azure write permissions before Azure reads. Determine one mode per invocation;
read Discovery inputs and write only that mode's output or an investigation. Never write
run-status.md. Independent modes may be concurrent if supported, otherwise sequential.

All findings require evidence, confidence, a risk tier, honest price basis and IaC match where
applicable; emit `proposed`. Follow `risk-tier-assessment`, `price-basis-handling`, and `iac-matching`.
Corroborate idle/anomaly hypotheses with independent signals. If disproved, record an evidence-led
investigation rather than forcing a finding.

| Mode | Work and skills | Output |
|---|---|---|
| waste | Investigate orphans, idle/stopped billed compute, dev/test schedules, storage tiers using `orphaned-resource-detection`, `idle-compute-detection`, `devtest-shutdown-schedules`, `storage-tiering-lifecycle`. Use observed windows and metrics. | `findings/waste.json` |
| rightsizing | Utilisation CPU/memory/network, target SKU and headroom with current/target prices; assess entitlement using `hybrid-benefit-eligibility`. Nonproduction downsize and AHB are T2; production compute T3. | `findings/rightsizing.json` |
| tagging | Use `tagging-policy-design` for taxonomy, fully tagged coverage, unallocatable spend and policy; compare to >90% target. Often T0 and $0; do not imply savings. | `findings/tagging.json` |
| commitment | Use `commitment-modelling` for reservations vs savings plans, 1y/3y break-even, coverage, flexibility and lock-in from reliable baseline; sparse evidence lowers confidence. Purchases T3, no PR. | `findings/commitments.json` |
| anomaly | Use `anomaly-explanation` to decompose spend delta, correlate activities and compare prior run anomalies and `anomalyCount`; missing prior baseline means unavailable trend. Attempt cost query before fallback; never invent deltas. | `findings/anomalies.json` or investigation |
| verify | Apply `savings-verification` only to actually merged findings with `mergedAt` and baseline; require default ≥7-day settling and ~3-day cost lag. If too fresh or cost unavailable, inconclusive. Resource-state evidence alone is not cost confirmation. Compare baseline and observed costs, classify confirmed/partial/not-observed/inconclusive; update finding to verified only on confirmed. | `verification/<finding-id>.json` |

Use the bundled `validate-findings.py <absolute-output>` (entry skill explains installed paths)
for each nonempty finding/verification file. Inspect investigation-only records instead; empty
targets are validation failures. Report files and blockers for orchestrator artifact checks.
