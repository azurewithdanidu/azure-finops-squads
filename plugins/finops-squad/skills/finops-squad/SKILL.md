---
name: finops-squad
description: Run, resume or verify a read-only Azure FinOps audit with approved Bicep PR remediation. Use when auditing Azure spend, ranking findings or verifying savings. Do not use for generic Bicep review, deployment or non-Azure costs.
---

# FinOps squad entry

Load the binding [safety contract](references/safety-contract.md) and
[capability map](references/capability-map.md) for every invocation, including direct specialist
entry. The human must confirm no effective Azure write access, including inherited and activated
roles, before **any** Azure query; stop if not confirmed. The local preflight cannot establish RBAC.

## Installed assets and workspace preflight

Identify the absolute path of this installed `finops-squad/SKILL.md` using the host's skill
resolution. Its parent is the entry skill directory; scripts are in its `scripts` child and schemas
in its `schemas` child. Do not assume the consumer cwd contains scripts or a source clone. Resolve
and quote the absolute script paths, and pass an absolute consumer workspace and absolute run
paths. If the host cannot resolve this skill's location or the workspace, stop and report that
limitation; do not guess a client-specific variable.

Before any private artifact write or Azure query run:

`python -B "<absolute-entry-skill-dir>/scripts/preflight.py" --workspace "<absolute-consumer-workspace>"`

Stop on missing config, missing `.finops` ignore coverage, or any preflight error. If config is
missing, use the [synthetic example](references/templates/config.example.json) to guide its
creation only in the ignored consumer workspace. Do not silently change ignore rules. Stop before
Azure if the separate mandatory human RBAC confirmation above is absent. Configuration, run
state, reports and approved IaC edits belong in the consumer workspace, never the plugin
installation.

For all bundled commands, `python -B "<absolute-entry-skill-dir>/scripts/<script>.py"` is the
executable form; `--workspace`, `<run>`, findings and runs directory arguments must be absolute.
Python scripts resolve schemas relative to their own `__file__`.

## Orchestrate

1. Read config and scope, create a unique `.finops/runs/<yyyymmdd-hhmm>` under the workspace and
   initialize its status using `run-orchestration`. An optional
   `iteration-brief` records business goals.
2. With explicit human confirmation at each handoff, invoke `finops-discovery`,
   then applicable `finops-analysis` modes. If the host supports concurrent
   specialists, independent modes may run concurrently, each writing only its own artifacts.
   Otherwise run sequentially with the same contracts; correctness never depends on concurrency.
3. Check artifacts, not summaries, with `phase-delegation`.
   Validate discovery using the bundled `validate_discovery.py <absolute-run> --strict` and each
   nonempty findings/verification target using `validate-findings.py <absolute-target>`.
   Retry a failed phase at most once, then record the blocker. Never retry an inconclusive
   verification as failure. Only the orchestrator writes `run-status.md`.
4. Rank by estimated saving weighted by confidence, tier and effort separately; explain trade-offs
   and iteration constraints. Recheck tiers. Write `plan.md` with scope, ranked findings and
   approval gate. Stop for explicit user approval before invoking `finops-remediation`;
   never auto-chain to it. Approved PRs are not merged by the squad.
5. After actual merge, record the PR's actual `mergedAt`, then, once settled, run analysis `verify`
   and `finops-reporting` with user confirmation at handoffs. If not merged,
   report pending. For resume, recheck every claimed-complete artifact and restart from the earliest
   failed check. Reports and an optional retrospective distinguish estimated from realised savings.

When tools or inputs are unavailable, record the gap and stop or continue only with supported
evidence. Never fabricate spend, tiers, permissions or realised savings.
