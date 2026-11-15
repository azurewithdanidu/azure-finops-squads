---
title: finops-squad
description: Source repository for an installable Azure FinOps agent plugin.
---

## finops-squad

An installable, IDE-first Azure FinOps workflow: read-only discovery, evidence-backed findings,
ranked opportunities, static reports, explicitly approved Bicep PRs and later savings verification.
There is no interactive dashboard or live Azure remediation.

The installable package is [plugins/finops-squad](plugins/finops-squad/README.md).
This repository is its development source, not a consumer workspace template.

## Try the plugin locally

Load `plugins/finops-squad` using your client's local plugin support. With Copilot CLI:

```powershell
copilot --plugin-dir "D:\path\to\azure-finops-squads\plugins\finops-squad" --agent finops-squad:finops-orchestrator
```

In the consumer's IaC workspace, select `finops-orchestrator` or ask:

> Run a read-only FinOps audit using my local configuration. Rank the findings and write reports.
> Do not remediate or open PRs.

The recommended entry skill is `finops-squad`. Five thin agent wrappers route to discovery,
analysis, remediation and reporting skills. Their domain knowledge is loaded on demand.
Where subagents are unsupported, the same contracts can run sequentially in one session.

Copilot CLI requires the qualified agent name shown above; the unqualified agent name is rejected.
The clean-consumer CLI loading and permission-refusal smoke test passes. Live Azure access and
other clients remain unverified.

See [getting started](docs/getting-started.md) for private local configuration and prerequisites.
Marketplace installation is pending publication and a commit-pinned linked entry in agentz;
no marketplace install command is claimed to work yet.

## Safety and output

- Confirm the Azure identity has no effective write access before live queries.
- Keep evidence, confidence, price basis and currencies explicit.
- Stop for finding-specific approval before preparing any remediation PR.
- Refuse T3 or untiered changes. T2 requires separate confirmation and a draft PR.
- Never deploy, automatically merge, or change live Azure resources.
- Treat savings as realised only when later observed cost data supports them.

Reports are Markdown/JSON under the consumer's Git-ignored `.finops/` directory. Installed plugin
files remain unchanged. Configuration, scope identifiers and customer evidence must never be
copied into the distributable package.

## Develop and validate

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python scripts/plugin_tools.py --agentz-root "D:\path\to\agentz" --sync
npx -y @microsoft/vally-cli@0.20.0 lint plugins/finops-squad/skills --eval-spec plugins/finops-squad/evals/eval.yaml
```

`plugin_tools.py` reuses agentz's manifest generators and full structural gate in a temporary
local marketplace. It does not modify the real marketplace or fabricate a publication SHA.
Omit `--sync` to check that generated client files are current.

Python tests cover deterministic policy and data handling, not real agent behaviour or Azure
permissions. Vally behavioural evaluations require Copilot authentication.

> [!WARNING]
> Run model evaluations only in a disposable, isolated worker with no Azure/AWS credentials,
> inherited cloud configuration or user customisations. Vally's temporary workspace is not an
> OS sandbox. Shell/write/network simulations reduce risk but are not a complete security boundary.
> Do not run these commands directly on a shared workstation.

Inside that isolated worker:

```powershell
npx -y @microsoft/vally-cli@0.20.0 eval --eval-spec plugins/finops-squad/evals/eval.yaml --workers 1 --require-pass
```

Only claim client compatibility after an actual installation test; generated manifests alone do
not certify VS Code, Claude Code or Cursor behaviour.

## Repository layout

```text
plugins/finops-squad/    # distributable source, generated client definitions and Vally evals
tests/                  # development regression tests and synthetic fixtures
scripts/plugin_tools.py # isolated marketplace generation and validation
docs/                   # source-repository contributor and release documentation
```

See [architecture](docs/architecture.md), [security model](docs/security-model.md),
[skill authoring](docs/skill-authoring-guide.md) and the [migration plan](docs/plugin-migration-plan.md).

## License

[MIT](LICENSE).
