---
description: Rules for reading and writing finops-squad run artifacts under .finops/.
applyTo: ".finops/**"
---

# Findings and run-artifact rules

Everything an agent reads or writes under `.finops/` follows these rules.

## Schema compliance

- Every entry in `findings/*.json` must validate against
  [finding.schema.json](../../schemas/finding.schema.json).
- Every file in `verification/*.json` must validate against
  [verification.schema.json](../../schemas/verification.schema.json).
- Run `python scripts/validate-findings.py .finops/runs/<id>/` before any handoff. Do not hand off
  invalid artifacts.

## Field discipline

- `id`: `^[a-z]+-[0-9]{4}$`, stable for the life of the finding (e.g. `waste-0001`).
- `estimatedMonthlySaving.basis`: always `list-price` or `actual`, never blank. Use `actual`
  only when backed by a real EA/MCA/CSP/PAYG rate.
- `evidence`: at least one entry, each with `capability`, `tool`, `query`, `timeWindow`,
  `observation`. No finding without evidence.
- `tier`: always set (`T0`–`T3`). A missing tier is treated as unactionable by the Implementer.
- `iacMatch.status`: `found`, `not-found`, or `unmanaged`. `unmanaged` means the Implementer
  produces a documented manual change request instead of a PR.

## Status ownership

- `status` transitions (`proposed → approved → pr-open → merged → verified | rejected`) are owned
  **only** by the orchestrator, the Implementer, and the Analyser (in `verify` mode). Finding
  agents always emit `proposed`.
- The same ownership discipline applies to `.finops/runs/<id>/run-status.md` (the pipeline-progress
  dashboard, distinct from each finding's own `status` field — see
  [run-orchestration](../skills/run-orchestration/SKILL.md)): every agent re-reads the file
  immediately before writing it, edits only its own row, and never downgrades a row from ✅ to an
  earlier state or reverts another agent's timestamp. On a write conflict, replay the edit onto the
  latest copy (up to 3 retries) before recording a blocker and stopping.

## Investigations (checked, no finding)

When an agent investigates something that *looked* like a finding (e.g. a high-cost resource with
a suspicious metric) but the evidence does not actually support one, **do not force a finding**.
Instead, write an investigation record to `investigations/<slug>.json` with: `subject`, `trigger`,
`result` (e.g. `"NOT a finding -- investigation retracted the <hypothesis>"`), `evidence[]` (same
shape as finding evidence), and `conclusion`. This preserves the negative result for audit and
avoids repeat investigation of the same resource. Investigation files are not schema-gated like
findings, but must still follow the evidence-over-opinion rule — no asserted conclusion without
cited evidence.

## Honesty

- Never invent cost numbers. Attempt `cost.query_spend` first; only say "spend data unavailable"
  if the call genuinely fails — do not assume unavailability without trying.
- Label estimates as estimates; a saving becomes `realised` only via an Analyser `verify`-mode
  record.
- Never conclude a resource is idle/wasteful from a single metric — corroborate with at least one
  more independent signal before writing a finding (see
  [idle-compute-detection](../skills/idle-compute-detection/SKILL.md)).
