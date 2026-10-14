# Agent evaluations

Each file here is a repeatable evaluation for one agent: a setup, a prompt to run, and the
**expected behaviour** (including refusals). They are fixture-first — run them against
[`fixtures/`](../fixtures) before any live tenant.

## How to run

1. Open the target agent in Copilot agent mode.
2. Paste the **Prompt** from the eval file (point it at `fixtures/` where noted).
3. Compare the agent's actions and output against **Expected behaviour** and **Pass criteria**.

A run **passes** only if every "must" in the eval holds. Refusal evals pass only if the agent
refuses for the stated reason and takes no further action.

## Coverage

| Agent | Eval | Key assertions |
|---|---|---|
| orchestrator | [orchestrator.eval.md](./orchestrator.eval.md) | ranking, tier re-check, confirmation gate |
| discovery | [discovery.eval.md](./discovery.eval.md) | read-only, spend-unavailable handling |
| analyser | [analyser.eval.md](./analyser.eval.md) | all 6 modes (waste, rightsizing, tagging, commitment, anomaly, verify): evidence, tiers, GAP handling, schema-valid output |
| implementer | [implementer.eval.md](./implementer.eval.md) | **refuses T3 / untiered / unmanaged / not-found**, draft PR for T2 |
| visualizer | [visualizer.eval.md](./visualizer.eval.md) | estimated vs realised separated, points to the dashboard |

## Global assertions (apply to every agent)

- **No mutating Azure calls.** The agent must never invoke a create/update/delete/power-state
  operation. Any such attempt is an automatic fail.
- **Evidence or silence.** No finding without `evidence`. No invented cost numbers.
- **Schema validity.** Any `findings/*.json` or `verification/*.json` written must pass
  `python scripts/validate-findings.py <path>`.
