---
description: Run a full FinOps audit — Discovery gathers data, the Analyser runs each applicable mode, then the Visualizer summarizes. Stops before any remediation.
---

# Run audit

Run a read-only FinOps audit over the subscriptions in `.finops/config.json`.

1. Invoke **finops-orchestrator** to scope the run and create `.finops/runs/<timestamp>/`.
2. Run **finops-discovery** to produce `inventory.json`, `spend.json`, `advisor.json`.
   - Discovery tries `arm.query_costs` first. If it genuinely fails, continue and mark spend
     unavailable with the real error — do not fabricate numbers.
3. Run **finops-analyser** once per applicable mode for this wave — at minimum `waste`, and if
   configured also `tagging`, `rightsizing`, `anomaly`. Each mode writes schema-valid
   `findings/*.json` (or `investigations/*.json` if a hypothesis doesn't hold up).
4. Have the orchestrator rank findings and write `plan.md`.
5. Run **finops-visualizer** to produce `reports/executive-summary.md`,
   `reports/engineer-backlog.md` and `reports/savings-ledger.json`.

**Stop here.** Do not hand anything to the Implementer. Present the ranked findings and wait for
the user to approve remediation.

Validate before finishing: `python scripts/validate-findings.py .finops/runs/<id>/`.
