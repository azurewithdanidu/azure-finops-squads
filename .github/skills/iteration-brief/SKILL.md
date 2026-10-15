---
name: iteration-brief
description: Capture an optional, lightweight FinOps iteration brief (goal, baseline, target, measurement window) so a run serves a stated business outcome instead of only producing a one-off finding list. Use when starting a run, closing one out, or asked to plan the next iteration.
---

# Iteration brief

Borrowed from the FinOps Framework's Inform → Optimize → Operate cycle: a short, bounded
iteration with 1-3 measurable goals beats an open-ended audit. This is **optional** — a user who
only wants a one-off engineering scan should never be forced through this.

## When to use

- At the start of a run, when the user has (or can be asked for) a specific outcome in mind.
- At the end of a run, to carry a goal's baseline/target forward into the next iteration (see
  [finops-reporting](../finops-reporting/SKILL.md) for the matching retrospective).
- Never required to produce `findings/*.json` — a run with no brief still runs exactly as before.

## Inputs

| Source | Role |
|---|---|
| User's stated goal (if any) | What outcome this iteration should move |
| Prior run's `iteration.md` / `reports/retrospective.md` (if continuing an iteration) | Baseline and target already set; don't re-derive from scratch |
| `.finops/config.json` | Scope (subscriptions, price basis) the brief inherits |

## Outputs

| Artifact / field | Result |
|---|---|
| `.finops/runs/<id>/iteration.md` | The human-readable brief — see [references/iteration-brief-template.md](references/iteration-brief-template.md) |
| `.finops/runs/<id>/iteration.json` | The same brief's key fields, structured, so the dashboard and retrospective can read it without parsing prose — see [references/iteration-brief-template.md](references/iteration-brief-template.md) for the paired JSON shape |
| `iterationId` (free-text, user-chosen) | Lets multiple runs be grouped into one iteration for the retrospective and dashboard, without a new folder structure |

## Method

1. Ask (or infer from context) whether this run serves a specific outcome. If the user just wants
   a scan, skip this skill entirely — do not block or nag.
2. If there is a goal: capture it with the template in
   [references/iteration-brief-template.md](references/iteration-brief-template.md) — **1 to 3**
   measurable goals, a real baseline (or an honest "unavailable: `<reason>`", never a guess), a
   target, and a measurement window. Consider knowledge, process, metrics, adoption and automation
   as dimensions worth stating — not just "did the scan run." Write both `iteration.md` (the
   narrative, for humans) and `iteration.json` (the same key fields, structured, so the dashboard
   and the Visualizer's retrospective don't have to parse prose).
3. Record explicit business constraints (guardrails) alongside the cost goal — e.g. "no production
   changes during business hours," "don't touch anything tagged `dr=true`." These feed the
   orchestrator's ranking (see [finops-orchestrator.agent.md](../../agents/finops-orchestrator.agent.md))
   without inventing a universal "business value" score.
4. State what's explicitly out of scope, so a later reviewer can tell deliberate exclusion from an
   oversight.
5. At close-out, hand the brief (goal, baseline, target) to the Visualizer for the retrospective.

## Rules / Pitfalls

- **Never fabricate a baseline.** If spend/inventory data for the baseline metric is genuinely
  unavailable, say so in the brief — the same honesty rule as every other artifact in this squad.
- **Don't invent a single "business value" score.** The brief's constraints and goals inform the
  orchestrator's ranking narrative; savings, confidence, effort, risk and `iacMatch` stay separate,
  auditable dimensions (see [risk-tier-assessment](../risk-tier-assessment/SKILL.md)).
- **A bounded scope beats a broad one.** 1 to 3 capability areas per iteration (the FinOps
  Framework's own starting guidance); don't try to cover every mode every time.
- **Don't force this on a one-off audit.** If there's no iteration brief, every other agent and
  skill in the squad must behave exactly as if this skill doesn't exist.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| FinOps Framework overview | https://learn.microsoft.com/en-us/cloud-computing/finops/framework/finops-framework |
| Conducting a FinOps iteration | https://learn.microsoft.com/en-us/cloud-computing/finops/conduct-iteration |
| FinOps best-practice library | https://learn.microsoft.com/en-us/cloud-computing/finops/best-practices/library |

### Key takeaways

- An iteration is bounded and measurable — a goal, a baseline, a target, a window — not an
  open-ended "find savings" mandate.
- Optional by design: this skill must never become a gate that blocks a simple one-off scan.
- Constraints are as important as the goal — a guardrail that overrides a savings-only ranking is
  a feature, not noise to filter out.
