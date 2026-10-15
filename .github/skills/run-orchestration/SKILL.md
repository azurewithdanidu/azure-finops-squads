---
name: run-orchestration
description: Keep a run's shared status dashboard (run-status.md) synchronised across phases and parallel modes, with ownership rules, a status legend, and a resume procedure. Use when starting, updating, or resuming a finops-squad run.
---

# Run orchestration

`plan.md` records the ranked, approved findings for a run. `run-status.md` is a separate, lighter
file: a live phase dashboard so a run can be checked or resumed without replaying the chat history.

## When to use

- Starting a new run (write the initial dashboard).
- After any phase or Analyser mode hands off (update its row).
- Resuming an interrupted run.
- Whenever more than one agent can touch the same run folder in the same turn (the parallel
  Analyser modes).

## Inputs

| Source | Role |
|---|---|
| `.finops/runs/<id>/run-status.md` (if it exists) | Current phase state to re-read before every write |
| Each phase/mode's output artifact | Evidence used to verify a row before marking it ✅ |

## Outputs

| Artifact / field | Result |
|---|---|
| `.finops/runs/<id>/run-status.md` | Live phase dashboard — status legend, phase table, blockers |

## The dashboard: `.finops/runs/<id>/run-status.md`

```markdown
# Run status — <yyyymmdd-hhmm>
Last updated: <UTC ISO-8601>

## Status legend
| Symbol | Meaning |
|---|---|
| ⏳ | Not started |
| 🔄 | In progress |
| ⏸ | Awaiting user confirmation |
| ✅ | Complete |
| ❌ | Failed / blocked |

## Phase summary

| Phase | Agent | Artifact | Status | Completed at |
|---|---|---|---|---|
| Discovery | finops-discovery | inventory.json, spend.json, advisor.json | ⏳ | — |
| Analyse — waste | finops-analyser (waste) | findings/waste.json | ⏳ | — |
| Analyse — rightsizing | finops-analyser (rightsizing) | findings/rightsizing.json | ⏳ | — |
| Analyse — tagging | finops-analyser (tagging) | findings/tagging.json | ⏳ | — |
| Analyse — commitment | finops-analyser (commitment) | findings/commitments.json | ⏳ | — |
| Analyse — anomaly | finops-analyser (anomaly) | findings/anomalies.json | ⏳ | — |
| Rank | finops-orchestrator | plan.md | ⏳ | — |
| Confirm | user | — | ⏳ | — |
| Implement | finops-implementer | PR(s) | ⏳ | — |
| Verify | finops-analyser (verify) | verification/*.json | ⏳ | — |
| Visualize | finops-visualizer | reports/ | ⏳ | — |

## Blockers
- None
```

## Ownership and merge rules

- The orchestrator owns: initializing the file, the Rank/Confirm rows, and the final row.
- Each specialist agent updates only its own row when it finishes — never another agent's row.
- The five independent Analyser modes run in parallel and each touches only its own row and its
  own `findings/<mode>.json` file; none of them edits another mode's row.
- **Re-read `run-status.md` immediately before every write.**
- Never downgrade a row from ✅ to an earlier state without re-running and re-verifying that
  phase first.
- Never revert another phase's timestamp or status.
- If a conflicting edit is found on re-read, replay your row's edit onto the latest copy; retry up
  to 3 times; on the third failure add a `## Blockers` entry naming the row and stop.

## Timestamps

UTC ISO-8601 only, e.g. `2026-05-18T03:00:00Z`. No local time, no mixed offsets — this keeps the
resume procedure below deterministic.

## Resume procedure

1. Read `run-status.md`. If it's missing, recreate it from whatever artifacts already exist in the
   run folder, marking rows ✅ only after verification (step 2).
2. For every row marked ✅ or further, **re-verify its artifact still exists and still passes its
   minimum-content/schema check** — do not trust the recorded status alone.
3. Resume from the **earliest row whose artifact fails re-verification**, not from the latest row
   claimed complete.
4. Update `Last updated` and continue the pipeline from there.

## Pitfalls

- A ✅ is an evidence claim — only set it once the artifact file has actually been opened and
  checked, per [phase-delegation](../phase-delegation/SKILL.md).
- Don't let `run-status.md` duplicate or drift from `plan.md` or a finding's own `status` field:
  `run-status.md` tracks pipeline progress; each finding's `proposed → … → verified` lifecycle
  still lives only inside the finding JSON (see
  [findings.instructions.md](../../instructions/findings.instructions.md)).
- Keep this file to a phase table and a blockers list — it's a dashboard, not a replacement for the
  ranked detail in `plan.md`.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| ISO 8601 date and time format | https://www.iso.org/iso-8601-date-and-time-format.html |

### Key takeaways

- The dashboard is for humans resuming a run without replaying chat history — keep it skimmable,
  not exhaustive.
- Re-read-before-write is the one rule that makes the parallel Analyser modes safe to run
  concurrently against a shared file.
