---
description: Verify realised savings for merged findings after a settling period, then refresh the reports and ledger.
---

# Verify savings

Confirm whether merged remediations actually reduced cost.

1. Invoke **finops-analyser** in `verify` mode for each finding with `status: merged`.
   - Enforce a settling period (≥ 7 days after `mergedAt`) and allow for cost-data lag (~3 days).
   - Classify each as `confirmed`, `partial`, `not-observed`, or `inconclusive`.
   - Write `verification/<finding-id>.json` (schema-valid). Never mark a saving realised without
     observed cost data; if cost data is unavailable, verify resource change and mark cost
     `inconclusive`.
2. Rebuild the ledger: `python scripts/ledger.py .finops/runs/<id>/`.
3. Run **finops-visualizer** to refresh the executive summary and backlog with **realised** vs
   **estimated** savings clearly separated.

Validate: `python scripts/validate-findings.py .finops/runs/<id>/verification/`.
