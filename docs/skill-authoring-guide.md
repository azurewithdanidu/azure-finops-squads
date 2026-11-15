---
title: Skill authoring guide
description: Conventions for portable FinOps plugin skills and shared assets.
---

## Source layout

Author plugin content only under `plugins/finops-squad/`. Skills use
`skills/<name>/SKILL.md`; agents use `agents/<name>.agent.md`. Do not recreate workspace
`.github/agents/` or `.github/skills/` copies.

Each skill's frontmatter has a matching `name` and a 50-1024 character `description` with
specific "Use when" and "Do not use" clauses. Keep domain triggers specific to FinOps so they
do not steal generic AVM review or Bicep authoring requests from other plugins.

## Shared contracts and paths

The entry `finops-squad` skill owns the common safety/capability references, Python tools and
schemas. Other skills locate it by name and load the common safety contract explicitly.
Do not copy shared rules into each domain skill.

Use Markdown links only for resources inside the skill directory; invoke sibling skills by
name. Vally rejects Markdown references that escape a skill directory even when they resolve
inside the enclosing plugin.

Resolve bundled tools from the installed entry skill location. Use `python -B` with quoted
absolute tool and consumer paths; never use client-specific substitution variables in portable
skills or rely on a consumer-root `scripts/` directory.

## Behaviour and tests

Preserve evidence, approval, tier, currency and realised-savings contracts when changing skills.
The installed package remains unchanged; only consumer artifacts or specifically approved IaC
files may be written. Agents stay thin, with `name` and `description` frontmatter, no fixed
model and no host-specific tool list.

Every exposed skill needs a trigger case in the plugin's `evals/eval.yaml`. Add meaningful
negative, stop and safety cases. A global `diff-empty` is appropriate for refusal-only cases,
not for workflows expected to create private run artifacts.

Run the Python regressions, Vally lint and agentz structural gate. Regenerate client manifests
through `scripts/plugin_tools.py --agentz-root <checkout> --sync`; do not edit generated files.
Bump the plugin manifest version for subsequent source changes after its initial release.
