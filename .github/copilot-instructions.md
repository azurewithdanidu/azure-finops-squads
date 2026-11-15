---
description: Development rules for the FinOps squad plugin source repository.
---

# FinOps squad source development

The installable product lives under `plugins/finops-squad/`. Do not create workspace copies of
agents or skills under `.github/`; these would load duplicate definitions.

The canonical runtime rules are in the plugin entry skill's
[safety contract](../plugins/finops-squad/skills/finops-squad/references/safety-contract.md).
Load that contract before operating any FinOps workflow. Never query Azure without explicit
confirmation of no effective write permissions, and never mutate live Azure.

Keep all customer configuration and runtime artifacts in the consumer's ignored `.finops/`
directory, never the distributable plugin. Do not copy real data into tests or prompts.

The plugin's generated client manifests are produced by `scripts/plugin_tools.py` using agentz
tooling. Edit source `plugin.json` and `.mcp.json`, not their generated client copies.

Run `python -m pytest tests -q` after code changes. Run Vally lint and the isolated marketplace
gate after changing packaged content. Do not claim that offline tests prove live permissions,
client compatibility or realised savings.
