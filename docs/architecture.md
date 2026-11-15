---
title: Architecture
description: Portable FinOps plugin components and artifact-based phase contracts.
---

## Package and workspace separation

The distributable [plugin](../plugins/finops-squad/README.md) contains classic source definitions:
`plugin.json`, optional `.mcp.json`, five thin agents, skills, bundled Python tools/schemas and
Vally evaluations. Client manifests are generated with agentz tooling, never maintained manually.

The consumer workspace contains private `.finops/` configuration and run artifacts. The plugin
installation is read-only at runtime. Development tests and marketplace tooling remain outside
the distributable package.

## Workflow

```text
Preflight -> Discover -> Analyse -> Rank -> Confirm -> PR -> Merge observed -> Verify -> Report
```

`finops-squad` is the entry skill and `finops-orchestrator` its agent wrapper. The discovery,
analysis, remediation and reporting phase skills carry the real workflow; the other agents
delegate to those skills. Domain skills provide reusable detection and remediation knowledge.

The orchestrator alone writes run-status. Independent analysis modes may run concurrently if
the client supports subagents; otherwise they run sequentially with the same artifact checks.
Do not treat chat summaries as completion evidence. Validate actual artifacts and retry within
the bounded phase contract.

The bundled safety contract is loaded explicitly by skills and agents. Consumer workspaces do
not inherit this source repository's `.github/` instructions.

## Data contracts

Finding, spend and verification schemas live beside the entry skill's scripts, resolved relative
to `__file__`. Scripts accept explicit run paths, so the consumer's working directory is not an
implicit source of code.

The entry preflight checks private storage and configuration. It does not query Azure or prove
RBAC. Deterministic remediation checks reject unapproved, T3, missing-IaC and unconfirmed changes,
but confirmation flags do not independently prove human consent.

Ledger and KPI tools preserve currency boundaries and distinguish estimates from observed
savings. Daily spend/event logic excludes provisional days. Run comparisons match by type and
resource ID, not per-run finding ID; absence alone is not proof of remediation.

## Portability and release

Capabilities depend on the host's available Azure tools. The package does not promise that
installing Azure MCP creates every host-specific cost tool.

`scripts/plugin_tools.py` stages a local marketplace, runs agentz's generators/catalog/gate,
and optionally refreshes generated plugin client files. A real linked release additionally
needs a published source commit, full commit SHA, package subdirectory and marketplace approval.

See [security model](security-model.md) for enforcement limits and the
[migration plan](plugin-migration-plan.md) for release acceptance criteria.
