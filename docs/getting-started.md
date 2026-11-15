---
title: Getting started
description: Load the FinOps plugin in an IaC workspace and run a read-only assessment.
---

## Load the package

Load [plugins/finops-squad](../plugins/finops-squad/README.md) with the client's local plugin
support, not the repository root. Start a new chat after loading so the skills and agents are
discovered. In Copilot CLI, use
`copilot --plugin-dir "<absolute-package-directory>" --agent finops-squad:finops-orchestrator`.

The generated manifests support the classic plugin layout. Live client compatibility and Azure
tool availability must be checked in your client; they are not guaranteed by installation.

## Prepare the consumer workspace

Use your own Bicep IaC Git repository. Keep configuration only in its `.finops/config.json`.
With user permission, add `.finops/` to the consumer repository's ignore rules before creating
private artifacts. Never put configuration into the installed plugin.

Use the synthetic configuration template bundled with the `finops-squad` entry skill. Replace
sample scope values locally, select the cost window and price basis, and set the IaC repository
path. Install Python 3.10+ and `jsonschema` for the offline tools. The plugin also requires Git.

The entry workflow runs a local preflight that checks configuration and ignore coverage. It
does not validate Azure permissions. Use a dedicated audit identity with Reader, Cost Management
Reader and Monitoring Reader access and confirm no effective writes, including inherited,
group and activated eligible roles. See [security model](security-model.md).

## Connect tools

The optional bundled `finops-azure` MCP server uses Microsoft Azure MCP. Node.js and npx are
needed if this server is enabled. If the client already has equivalent Azure tools, disable
duplicate server registration in the client.

Discover inventory, spend, Advisor, metrics and pricing capabilities in the actual host.
Host-specific `arm` tools are not guaranteed. Missing data must be reported honestly rather than
turned into zero spend, zero resources or fabricated savings.

## Run and interact

Select `finops-orchestrator` or invoke the `finops-squad` skill:

> Run a read-only FinOps audit using my local configuration. Present the ranked findings,
> evidence and reports. Do not remediate or open PRs.

The workflow writes run artifacts into the consumer's ignored `.finops/runs/` directory.
Open its executive summary, backlog, ledger and KPIs directly in the editor.

Useful follow-up requests:

- Resume this run and explain its blockers.
- Compare this run with the previous run.
- Prepare a Bicep PR for the specific finding I approve.
- Verify this merged finding after its settling period and refresh the reports.

There is no automatic transition to a PR, no automatic merge and no deployment. T3 findings
remain analysis-only; T2 needs separate confirmation and a draft PR.

## Offline testing

Run the development repository's `python -m pytest tests -q` before any live assessment.
Plugin Vally fixtures contain only synthetic evidence. They are not observations of your estate.

Bundled scripts are resolved from the installed entry skill's directory and invoked with
`python -B`, using absolute consumer run paths. Never assume the consumer has a root `scripts/`
directory. A failed schema check blocks handoff; `jsonschema` is mandatory.
