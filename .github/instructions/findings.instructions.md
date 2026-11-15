---
description: Canonical runtime contracts for consumer-local FinOps artifacts.
applyTo: ".finops/**"
---

# FinOps artifacts

Load the plugin's [safety contract](../../plugins/finops-squad/skills/finops-squad/references/safety-contract.md).
The `finops-squad` entry skill owns bundled schemas and validators; do not assume root `schemas/`
or `scripts/` directories in the consumer workspace.

Only the orchestrator writes run-status. Findings and verification records require full schema
validation before handoff; an empty target or a missing dependency is not validation success.
Do not treat estimates as realised savings or unavailable evidence as a negative finding.
