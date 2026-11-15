---
title: FinOps squad plugin migration plan
description: Approved migration plan and implementation status for the FinOps squad plugin.
---

## Status and scope

Approved for implementation by the user's "Yes execute this" instruction. Source packaging is
implemented; marketplace publication remains a separate approval. See the
[readiness report](../.agentz/finops-squad/readiness-report.md) for observed validation and limits.

The package has five thin agents, 27 skills and three schemas, including four new workflow skills.
The migration preserves the approved dashboard removal and hardening work. The external agentz
checkout supplies validation tooling only and is not changed.

## Recommended approach

Keep this repository as the source of truth. Package the installable content under
`plugins/finops-squad/`, then register it in agentz as a linked plugin pinned to a full commit.
Do not maintain a second manually copied implementation in agentz.

Use the same classic plugin format as the reference: source `plugin.json`, `agents/`, `skills/`,
`evals/eval.yaml`, `README.md` and an optional `.mcp.json`. Generate client manifests through the
marketplace tooling rather than authoring them by hand.

Keep five thin agent wrappers for the initial migration. The orchestrator remains the recommended
entry point; avoid mixing packaging changes with a behavioural consolidation. Specialist agents
may still be visible in a client's picker. Do not promise that they are hidden.

Move phase logic into skills so loading an agent is not the only way to obtain the workflow.
Retain domain skills initially; consolidate only where trigger overlap or evaluation cost
justifies it. Do not mechanically expose all 23 existing skills unchanged.

## Proposed package

```text
plugins/finops-squad/
  plugin.json
  README.md
  .mcp.json                         # only if the verified configuration is needed
  agents/
    finops-orchestrator.agent.md
    finops-discovery.agent.md
    finops-analyser.agent.md
    finops-implementer.agent.md
    finops-visualizer.agent.md
  skills/
    finops-squad/
      SKILL.md                     # entry, safety, routing and approval gates
      references/
        safety-contract.md
        capability-map.md
      scripts/                     # shared offline tools, one canonical copy
      schemas/                     # schemas used by those tools
    finops-discovery/
      SKILL.md
    finops-analysis/
      SKILL.md
    finops-remediation/
      SKILL.md
    finops-reporting/
      SKILL.md
    <retained-domain-skills>/
      SKILL.md
      references/
  evals/
    eval.yaml
    fixtures/
```

Final domain-skill names and grouping follow the catalog overlap check. Existing reporting
knowledge can evolve into the reporting phase skill rather than creating duplicate triggers.

Only generated after integration with marketplace tooling:
`.claude-plugin/`, `.cursor-plugin/` and `mcp.json`.

## Required plugin definitions

The migration includes definitions and registration, not only moving agent and skill folders.

| Definition | Required content | Ownership |
|------------|------------------|-----------|
| `plugin.json` | `name: finops-squad`, semantic `version`, description, author name/email, source repository, MIT license and keywords | Source |
| `.mcp.json` | `mcpServers` with verified server definitions, if bundled MCP servers are needed; no credentials or subscription configuration | Source |
| `agents/*.agent.md` | Matching filename/name and description; thin skill delegation; no fixed model or host-specific tool grants | Source |
| `skills/*/SKILL.md` | Matching folder/name, trigger and exclusion description, prerequisites, workflow, safety and completion contract | Source |
| `evals/eval.yaml` | Vally configuration, skill trigger coverage, negative cases and checkable safety/task assertions | Source |
| `README.md` | Owner, beta status, format, tested platforms, prerequisites, installation and usage | Source |
| Agentz marketplace entry | Plugin name, description, allowed category and linked GitHub source with full commit SHA and package subdirectory | Marketplace source |
| Agentz `CODEOWNERS` entry | Responsible owner for the linked plugin entry | Marketplace source |
| `.claude-plugin/`, `.cursor-plugin/`, `mcp.json` | Client-specific definitions produced by the marketplace generators | Generated |

Use only manifest fields allowed by agentz. Do not add an Agent Plugins `$schema`,
`extensions`, or a `com.github.copilot/` directory. Do not manually maintain generated client
definitions. For the linked entry, specify `path: plugins/finops-squad` so installation resolves
the package rather than treating this entire development repository as the plugin.

Confirm author metadata before publishing. The manifest's repository points to this source
repository, not to the Bicep review example or the marketplace.

## Design constraints

### Installation paths and runtime state

Resolve bundled Python scripts and schemas from the installed plugin location, not from an
assumption that the consumer has a `scripts/` directory. Python tools should resolve package
assets relative to `__file__` and accept the consumer's run directory explicitly.

Define a documented, client-tested way to resolve the entry skill's directory. Keep
client-specific substitutions out of portable skills; verify their behaviour in supported
clients rather than assuming a universal plugin-root variable.

Keep `.finops/config.json`, runs, reports and approved IaC edits in the consumer workspace.
Never write customer data into the plugin cache or automatically alter the consumer's ignore
rules without consent. Detect absent `.finops/` ignore coverage before writing private artifacts.

### Instructions must travel with the plugin

The source repository's `.github/copilot-instructions.md` and path-specific instructions will
not automatically protect unrelated consumer workspaces. Extract their binding rules into the
bundled safety contract, explicitly loaded by every phase skill and referenced by every agent.

Preserve read-only identity confirmation, evidence, T0-T3 gates, actual/list-price distinctions,
currency separation, explicit PR approval and no automatic deployment or merging.

Agents use the reference plugin's portable frontmatter: `name` and `description`, without
host-specific tool grants or a hard-coded model. Instructions are not a security boundary;
effective read-only Azure permissions remain a prerequisite.

### MCP and host capabilities

Do not copy the repository's VS Code MCP configuration unchanged. Plugin MCP configuration uses
`mcpServers`, while the existing workspace example uses `servers`.

Discover and test required inventory, cost, Advisor, metric and pricing capabilities per client.
Do not advertise host-provided `arm` tools as universally installed by the plugin. Missing
capabilities produce explicit limitations, never fabricated negative results.

Bundle only required Microsoft MCP backends, without credentials or scope identifiers. Evaluate
duplicate server registration when the consumer already has Azure MCP configured.

### Handoffs and approvals

Preserve artifact-based handoffs and orchestrator-only run-status writes. Where client-supported
subagents exist, use bounded specialists; where they do not, run phases sequentially in one
session with the same contracts. Do not require concurrent agent execution for correctness.

Preserve the deterministic remediation check, but document that confirmation flags are assertions,
not independent proof of human consent. A successful check does not authorise a PR by itself.

## Migration phases

### 1. Confirm intent and reuse decision

- Approve the [intent brief](../.agentz/finops-squad/intent-brief.md), ownership and linked-source model.
- Review the [provisional catalog assessment](../.agentz/finops-squad/research.md): no match
  scored at least 0.4; closest was the static Bicep review skill at 0.22.
- Repeat component-level checks with the final skill descriptions and trigger phrases.
- Compare any matches scoring at least 0.4 against the requested workflow.
- Record reuse, extend or new; do not assume the reference review plugin covers live FinOps.

### 2. Establish the package skeleton

- Add the source manifest, README and proposed phase skills under `plugins/finops-squad/`.
- Convert agent bodies into thin skill wrappers with portable metadata.
- Move safety and capability contracts into the package and update relative links.
- Assign explicit positive and negative triggers to every retained skill.
- Do not remove the old discovery locations until the packaged equivalent passes validation.

### 3. Move code and assets without duplication

- Move reusable scripts, schemas and required synthetic fixtures into the package.
- Keep repository-level tests and CI in the development repository, pointing at packaged code.
- Update commands to use plugin-relative executables and explicit consumer run paths.
- Replace legacy prompt entry points with entry-skill workflows; add command wrappers only where
  tested client support warrants them.
- Remove obsolete `.github/agents/` and `.github/skills/` definitions after equivalence checks so
  the source workspace does not load duplicate components.
- Do not reintroduce dashboard code or dependencies.

### 4. Validate behaviour and installation

- Run existing offline regression tests against the moved code and schemas.
- Run a packaged workflow in a temporary consumer directory outside this repository.
- Use paths containing spaces, another working directory and read-only installed assets.
- Test run output placement, missing config, missing tools and missing Python dependencies.
- Add Vally trigger/no-trigger coverage for every exposed skill, plus approval refusal, T3,
  missing IaC, mixed currencies, invalid evidence, empty validation targets and inconclusive costs.
- Use scoped file-change expectations: audit phases may create `.finops/` artifacts, so a global
  `diff-empty` assertion would be wrong. Approved remediation may touch only the intended IaC.
- Exercise no-Azure fixture workflows first. Live queries still require read-only permission
  confirmation; a real PR and later savings verification require their separate gates and timing.
- Claim only platforms actually tested. Manifest generation alone is not a compatibility test.

### 5. Register and publish after approval

- Use an initial beta version such as `0.1.0`, confirmed against any existing catalog entry.
- Publish source changes only on explicit request; pin the linked marketplace entry to that commit.
- Add the linked entry and ownership in agentz using its documented workflow.
- Generate manifests and catalog, then run `scripts/validate_repo.py` from agentz.
- Run Vally lint and the behavioural evaluations before claiming publish readiness.
- Install from the resulting marketplace entry into a clean consumer workspace and repeat the
  smoke test. Do not run deployment or live remediation as part of installation.

## Acceptance criteria

- Installation does not require the consumer to clone this source repository.
- Required plugin definitions are present, marketplace-generated definitions are current, and
  the marketplace structural gate accepts the linked package and its subdirectory.
- One recommended chat entry point supports audit, resume, reports and verification.
- Code and assets have one canonical source; generated files are not maintained manually.
- Scripts work independently of the consumer's working directory.
- Installed plugin files remain unchanged during a run.
- No runtime subscription configuration, credentials or customer artifacts enter the package.
- Existing offline behaviours pass after relocation, and new installation-path cases pass.
- Approval, tier, evidence and estimate-versus-realised rules survive packaging.
- Missing client capabilities are visible and do not look like successful empty checks.
- Source-repository work and marketplace publication remain separate, approved changes.

## Approved decisions

1. Keep this repository as source and link it from agentz, rather than move development into agentz.
2. Retain the five agents for the packaging release, with one recommended orchestrator entry.
3. Target VS Code first, then claim Copilot CLI or other-client support only after testing.

Plugin source and generated definitions are implemented. The linked marketplace entry and
CODEOWNERS change remain deferred until a source commit is published with explicit approval.
