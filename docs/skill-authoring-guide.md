# Skill authoring guide

This defines the shape every `.github/skills/<name>/SKILL.md` follows, and when to use a
`references/` folder. It keeps finops-squad's existing terse voice (`Method`, `Pitfalls`) while
adding explicit contracts and a documented source trail.

## Folder shape

```
.github/skills/<skill-name>/
├── SKILL.md          # concise controller — never a monolith
└── references/        # optional-but-usual — catalogs, tables, snippets, worked examples
```

Scripts/steps subfolders are not used in this repo (no skill here is a multi-stage ordered
procedure big enough to warrant `steps/`) — keep that possibility in mind only if a future skill
genuinely has independent, prerequisite-linked stages.

## What goes in `references/` vs what stays in `SKILL.md`

- **Stays in `SKILL.md`:** the core decision logic a mode/agent needs on every invocation — the
  thing you'd read first every single time (thresholds, tier rules, the taxonomy, the core method).
- **Moves to `references/<topic>.md`:** content that's long, example-shaped, or reusable from
  multiple places — query catalogs, Bicep/JSON snippets, parameter tables, worked examples/war
  stories, break-even tables. `SKILL.md` should link to it, not inline it.
- **Never moves into a skill's `references/`:** repo-wide shared contracts — `schemas/*.json`,
  `scripts/*.py`, other skills' files. Those live at their existing shared locations; link to them,
  don't duplicate or relocate them into one skill's folder.
- Don't split a skill just because it's long if the content is one cohesive, single-read method —
  only split out genuinely separate, independently loadable material.

## `SKILL.md` template

```markdown
---
name: <skill-name>
description: <existing one-line description style — unchanged>
---

# <Title>

<One-paragraph Purpose, same as today's opening paragraph.>

## When to use

<Existing bullet list style — unchanged.>

## Inputs

| Source | Role |
|---|---|
| <tool / artifact / finding field> | <why this skill needs it> |

## Outputs

| Artifact / field | Result |
|---|---|
| <finding field, file, or decision this skill produces> | <what "done" looks like> |

## Method

<Existing numbered/prose method. Point to `references/<topic>.md` for catalogs, snippets, or
worked examples instead of inlining them.>

## Rules / Pitfalls

<Existing content — keep whichever heading the skill already uses.>

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|

### Key takeaways

- <2-5 bullets of hard-won lessons, distinct from the body Rules/Pitfalls>
```

Frontmatter stays at just `name` + `description` — this repo's `skill` tool has not been verified
to use `argument-hint`, `user-invocable`, or `disable-model-invocation`, so don't add them.

## Quality checklist

- [ ] Frontmatter has only `name` + `description`; `name` matches the folder name.
- [ ] Purpose paragraph says what and why in one paragraph.
- [ ] When to use has precise triggers, not "when needed".
- [ ] Inputs and Outputs tables are both present and accurate.
- [ ] Any catalog/table/snippet/worked-example over ~15 lines lives in `references/`, linked once.
- [ ] `## References` has a real Microsoft/Azure doc-link table (no placeholder links) and a short
      Key takeaways list.
- [ ] No schema, script, or another skill's file was copied or moved into this skill's folder —
      only linked.
- [ ] Every relative link (`references/...`, `../<skill>/SKILL.md`, `../../schemas/...`) resolves to
      a file that actually exists.

## Skill catalog — existing coverage

Use this to avoid duplication and find the right file to extend.

| Skill | Owning mode / agent | Covers |
|---|---|---|
| `orphaned-resource-detection` | Analyser — `waste` | Unattached disks/IPs/NICs, stale snapshots |
| `idle-compute-detection` | Analyser — `waste`, `rightsizing` | Utilization thresholds, network-appliance false positives |
| `devtest-shutdown-schedules` | Analyser — `waste` | Dev/test auto-shutdown schedules |
| `storage-tiering-lifecycle` | Analyser — `waste` | Blob access tiers + lifecycle rules |
| `hybrid-benefit-eligibility` | Analyser — `rightsizing` | AHB eligibility for Windows/SQL VMs |
| `tagging-policy-design` | Analyser — `tagging` | Tag taxonomy + Azure Policy enforcement |
| `commitment-modelling` | Analyser — `commitment` | Reservations vs savings plans |
| `anomaly-explanation` | Analyser — `anomaly` | Spend-spike decomposition and correlation |
| `savings-verification` | Analyser — `verify` | Confirming realised savings after merge |
| `advisor-cost-recommendations` | Discovery; seeds `rightsizing`/`commitment` | Reading/validating Advisor recommendations |
| `resource-graph-kql` | Discovery; Analyser `waste`/`tagging` | Resource Graph KQL query patterns |
| `cost-query-patterns` | Discovery; all cost-aware modes | `arm.query_costs` parameters and limits |
| `price-basis-handling` | All modes that set a saving | list-price vs actual labelling |
| `iac-matching` | Analyser (sets `iacMatch`); Implementer | Locating the Bicep source for a resource |
| `risk-tier-assessment` | All modes; Orchestrator re-check; Implementer gate | T0–T3 tiering |
| `bicep-avm-conventions` | Implementer | AVM/Bicep authoring style |
| `budget-and-alert-bicep` | Implementer | Budget/alert Bicep pattern |
| `pr-authoring` | Implementer | PR title/body template |
| `finops-reporting` | Visualizer | Report structure and honesty rules |
| `run-orchestration` | Orchestrator | `run-status.md` dashboard, resume |
| `phase-delegation` | Orchestrator | Per-phase invocation contract, bounded retry |
| `iteration-brief` | Orchestrator (optional); Visualizer (retrospective) | Bounded, measurable FinOps iteration goal/baseline/target/guardrails |
