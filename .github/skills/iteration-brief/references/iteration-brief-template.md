# Iteration brief template

A ready-to-fill template for `.finops/runs/<id>/iteration.md`. Keep every section short — this is
a brief, not a project plan.

```markdown
# Iteration brief — <iterationId, e.g. 2026-Q4-waste-01>
Run: <yyyymmdd-hhmm> · Capability area(s): <1-3 from the FinOps Framework capability list>

## Goals (1-3, measurable)
1. <e.g. "Reduce orphaned-resource spend in rg-dev by 80% of identified waste">
2. <...>

## Baseline
- Metric: <e.g. "estimated monthly waste in findings/waste.json">
- Value at iteration start: <amount + currency + basis, or "unavailable: <reason>">
- Captured: <date/run id this baseline came from>

## Target
- <value + currency> by <measurement window end date>

## Measurement window
<start> to <end> (e.g. "next 2 runs" or an explicit date range)

## Owner / stakeholder
<role or name responsible for acting on this iteration's findings>

## Constraints (business guardrails, not just cost)
- <e.g. "no change to production during business hours">
- <e.g. "do not touch anything tagged dr=true">

## Out of scope
- <explicitly excluded capability areas or resource groups, so scope creep is visible>
```

## Worked example

```markdown
# Iteration brief — 2026-Q4-waste-01
Run: 20261015-1245 · Capability area(s): Waste reduction, Tagging

## Goals (1-3, measurable)
1. Resolve the two orphaned public IPs and confirm IaC ownership for both.
2. Raise Owner-tag coverage from 4.1% to at least 50% via an audit-mode policy.

## Baseline
- Metric: findings/waste.json estimated saving; tagging-0001 missing-Owner count
- Value at iteration start: A$12.42/month (2 orphaned IPs); 467/487 resources missing Owner
- Captured: run 20261015-1245

## Target
- A$0 remaining orphaned-IP spend; missing-Owner count below 243/487 (50%) by end of window

## Measurement window
2026-10-15 to 2026-11-15 (next 3 scheduled runs)

## Owner / stakeholder
Platform team (Stuart Allan, per existing resource-group tags)

## Constraints
- No changes to the ExpressRoute gateway or production identity-tier VMs this iteration —
  those are tracked separately pending owner confirmation (see waste-0003, waste-0004).

## Out of scope
- Commitment modelling (baseline still unstable — see investigations/commitment-baseline-insufficient.json)
```

## The paired `iteration.json` shape

Write this alongside `iteration.md` with the same content, structured for the dashboard and
retrospective to read directly — never parse the Markdown prose for these fields.

```json
{
  "iterationId": "2026-Q4-waste-01",
  "runId": "20261015-1245",
  "capabilityAreas": ["Waste reduction", "Tagging"],
  "goals": [
    {
      "description": "Resolve the two orphaned public IPs and confirm IaC ownership for both.",
      "metric": "findings/waste.json estimated saving (orphaned-public-ip)",
      "baseline": { "value": 12.42, "currency": "AUD", "capturedAtRun": "20261015-1245" },
      "target": { "value": 0.0, "currency": "AUD" },
      "current": { "value": 12.42, "currency": "AUD", "capturedAtRun": "20261015-1245" }
    },
    {
      "description": "Raise Owner-tag coverage from 4.1% to at least 50%.",
      "metric": "tagging-0001 missing-Owner count / total resources",
      "baseline": { "value": 0.041, "capturedAtRun": "20261015-1245" },
      "target": { "value": 0.50 },
      "current": { "value": 0.041, "capturedAtRun": "20261015-1245" }
    }
  ],
  "measurementWindow": { "from": "2026-10-15", "to": "2026-11-15" },
  "owner": "Platform team (Stuart Allan)",
  "constraints": [
    "No changes to the ExpressRoute gateway or production identity-tier VMs this iteration."
  ],
  "outOfScope": ["Commitment modelling"],
  "status": "in-progress"
}
```

`goals[].current` is updated by whichever run last measured that metric — leave `baseline` and
`target` untouched across runs in the same `iterationId` so progress is comparable. `status` is one
of `in-progress`, `met`, `missed`, `abandoned` — set by the Visualizer at closeout, not guessed by
the dashboard.

