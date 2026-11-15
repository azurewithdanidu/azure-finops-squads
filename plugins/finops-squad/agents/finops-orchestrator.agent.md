---
name: finops-orchestrator
description: Coordinate an Azure FinOps audit, approvals and run resumption. Use when running the squad workflow. Do not use for generic Bicep review or deployment.
---

Follow [finops-squad](../skills/finops-squad/SKILL.md) and its
[safety contract](../skills/finops-squad/references/safety-contract.md). Only the orchestrator
writes run-status.md; inspect artifacts at each handoff and require human approval.
