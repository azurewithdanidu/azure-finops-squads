---
name: run-orchestration
description: Maintain the Azure FinOps run-status dashboard and resume checks. Use when starting, updating or resuming a squad audit. Do not use for general project status tracking.
---

# Run orchestration

Load the `finops-squad` skill, follow its preflight and its installed `references/safety-contract.md`.

`plan.md` records the ranked, approved findings for a run. `run-status.md` is a separate, lighter
file: a live phase dashboard so a run can be checked or resumed without replaying the chat history.

## When to use

- Starting a new run (write the initial dashboard).
- After any phase or Analyser mode hands off (the orchestrator updates its row).
- Resuming an interrupted run.
- Whenever more than one agent can touch the same run folder in the same turn (the parallel
  Analyser modes).

## Inputs

| Source | Role |
|---|---|
| `.finops/runs/<id>/run-status.md` (if it exists) | Current phase state, owned by the orchestrator |
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

- The orchestrator is the **only writer** of `run-status.md`, including phase rows and blockers.
- Specialists never write this file. They return their output paths and any blockers to the
  orchestrator, which verifies the artifacts and updates their rows.
- Independent Analyser modes may run concurrently where supported; otherwise run sequentially.
  Each writes only its own findings file or investigation output.
- Only one orchestrator session may own a run at a time; stop if another is active.
- Never downgrade a row from ✅ to an earlier state without re-running and re-verifying that
  phase first.
- Never revert another phase's timestamp or status.

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
  checked, per `phase-delegation`.
- Don't let `run-status.md` duplicate or drift from `plan.md` or a finding's own `status` field:
  `run-status.md` tracks pipeline progress; each finding's `proposed → … → verified` lifecycle
  still lives only inside the finding JSON (see
  the installed `finops-squad` safety contract).
- Keep this file to a phase table and a blockers list — it's a dashboard, not a replacement for the
  ranked detail in `plan.md`.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| ISO 8601 date and time format | <https://www.iso.org/iso-8601-date-and-time-format.html> |

### Key takeaways

- The dashboard is for humans resuming a run without replaying chat history — keep it skimmable,
  not exhaustive.
- A single orchestrator writer prevents parallel Analyser modes from overwriting status updates.
