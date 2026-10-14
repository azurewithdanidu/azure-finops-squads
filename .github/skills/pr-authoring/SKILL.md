---
name: pr-authoring
description: Write remediation PR titles and bodies with evidence, saving, tier, rollback and a verification plan. Use whenever the Implementer opens a PR.
---

# PR authoring

Every remediation PR must be self-explanatory and auditable.

## Title

`finops(<type>): <concise change> [<tier>]`
e.g. `finops(orphaned-disk): remove unattached disk-orphan-01 [T1]`

## Body template

```markdown
## What
<one-line change>

## Why (evidence)
- Finding: `<finding-id>` (<type>, tier <Tn>)
- Observation: <key evidence, e.g. diskState=Unattached for 90d>
- Source: <tool> — `<query/parameters>` over <timeWindow>

## Estimated saving
- **<amount> <currency>/month** (basis: <list-price|actual>, confidence: <low|med|high>)

## Risk & tier
- Tier <Tn>: <why this tier>
- Blast radius: <what this touches>

## Rollback
- <exact steps / Bicep to restore if needed>

## Verification plan
- After merge + settling period (≥7d, allow ~3d cost lag), the Analyser (in `verify` mode)
  re-checks <resource/cost slice> and records verification/<finding-id>.json.
```

## Rules

- **T2** findings → open as a **draft** PR and note that user confirmation was given.
- Never present the estimate as realised. Keep basis and confidence visible.
- Include a concrete rollback for any deletion/downsize.
- Link the finding id so the `verify`-mode run and ledger can correlate.
