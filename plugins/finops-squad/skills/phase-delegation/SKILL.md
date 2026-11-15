---
name: phase-delegation
description: Apply artifact-based handoff contracts to Azure FinOps audit phases. Use when orchestrating or checking a squad phase or mode. Do not use for generic multi-agent orchestration.
---

# Phase delegation

Load the `finops-squad` skill, follow its preflight and its installed `references/safety-contract.md`. Where specialist execution is unavailable, apply these same contracts sequentially.

Verify artifacts, not words: a sub-agent's chat reply is never proof that a phase succeeded. Read
the file it was supposed to write and check it against the table below.

## When to use

- Every handoff from the orchestrator to a specialist agent.
- Re-running a mode/phase that failed its artifact check.
- Auditing whether a phase actually produced enough output to count as complete.

## Inputs

| Source | Role |
|---|---|
| The target phase's declared required inputs (table below) | Confirmed to exist before delegating |
| The sub-agent's output file(s) on return | Read from disk — never the chat summary |

## Outputs

| Artifact / field | Result |
|---|---|
| Pass/fail verdict per phase | Drives whether `run-status.md` row moves to ✅ or a retry/blocker |

## Invocation contract per phase

| Phase | Agent | Required inputs | Required output(s) | Minimum-content check |
|---|---|---|---|---|
| Discovery | finops-discovery | `.finops/config.json` | `inventory.json`, `spend.json`, `advisor.json` | valid JSON; `spend.json` has numeric totals or a genuine `"status": "unavailable"` |
| Analyse — waste | finops-analyser (`waste`) | `inventory.json`, `spend.json` | `findings/waste.json` | validates against `finding.schema.json`; every entry has `evidence[]` and a `tier` |
| Analyse — rightsizing | finops-analyser (`rightsizing`) | `inventory.json`, `spend.json`, `advisor.json` | `findings/rightsizing.json` | same, `type: "rightsizing"` |
| Analyse — tagging | finops-analyser (`tagging`) | `inventory.json` | `findings/tagging.json` | same, `type: "tagging-gap"` |
| Analyse — commitment | finops-analyser (`commitment`) | `spend.json`, `advisor.json` | `findings/commitments.json` | same, tier `T3` |
| Analyse — anomaly | finops-analyser (`anomaly`) | `spend.json` | `findings/anomalies.json` or `investigations/<slug>.json` | same, or a valid investigation record |
| Rank / Confirm | finops-orchestrator | all `findings/*.json` | `plan.md` | ranked table present; explicit confirmation gate stated |
| Implement | finops-implementer | `plan.md` (approved subset) | PR, draft PR, or manual change request | finding `status` moved to `pr-open` with `prUrl`, or a manual-request Markdown for `unmanaged` |
| Verify | finops-analyser (`verify`) | merged finding + baseline | `verification/<finding-id>.json` | validates against `verification.schema.json` |
| Visualize | finops-visualizer | all run artifacts | `reports/*.md`, `savings-ledger.json` | files exist, non-empty |

## Process

1. Before delegating, confirm the phase's required inputs actually exist — read them, don't
   assume.
2. State the phase/mode and the required output path explicitly in the sub-agent prompt; don't
   leave the output location to the sub-agent's judgement.
3. After the sub-agent returns, **read the required output file(s) from disk.**
4. Run `python -B "<absolute-entry-skill-dir>/scripts/validate-findings.py" "<absolute-output-file>"` for every findings or verification
   JSON file produced. For investigation-only output, inspect the investigation record instead.
5. The orchestrator updates the matching row in `run-status.md` (see
   `run-orchestration`) only after the read in step 3 passes.
   Specialists never write that file.
6. If a check fails, follow the bounded retry procedure below.

## Bounded retry procedure

1. List the exact failing assertion(s): missing file, invalid schema, missing evidence, etc.
2. Re-invoke the **same** phase/mode once, stating only the failing assertions — don't widen scope
   or re-litigate a decision the user already approved.
3. Re-verify from disk again.
4. If it fails a second time (max **2 attempts** total), stop; the orchestrator adds a `## Blockers` entry to
   `run-status.md` naming the phase and the failing assertion, and report it to the user instead of
   retrying indefinitely.
5. **This retry loop never reaches the Implementer automatically.** A failed pre-PR Bicep check may
   be fixed and re-attempted before the PR is opened, but every PR still goes through the
   confirmation gate already owned by the orchestrator — retries never bypass human-in-the-loop.

## Pitfalls

- Don't retry a `verify`-mode `inconclusive` result as a failure — that's a correct, honest answer.
- Don't let a retry silently widen scope (e.g. re-running every mode when only `tagging` failed).
- A phase blocked by a genuine capability gap (e.g. commitments has no live backend) is not a retry
  case — it's an honest "no data" result; see
  `advisor-cost-recommendations` and `commitment-modelling`.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| JSON Schema validation | <https://json-schema.org/understanding-json-schema/> |

### Key takeaways

- "The sub-agent said it worked" is never sufficient — the only acceptable proof is the file on
  disk passing its stated check.
- Two attempts, then stop — a third silent retry just hides a real problem from the user longer.
