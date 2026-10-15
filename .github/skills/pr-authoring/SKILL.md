---
name: pr-authoring
description: Write remediation PR titles and bodies with evidence, saving, tier, rollback and a verification plan. Use whenever the Implementer opens a PR.
---

# PR authoring

Every remediation PR must be self-explanatory and auditable.

## When to use

- Every time the Implementer is about to open a PR (or draft PR) for an approved finding.

## Inputs

| Source | Role |
|---|---|
| Finding JSON (`id`, `type`, `tier`, `evidence`, `estimatedMonthlySaving`) | Everything the PR body must surface |
| [iac-matching](../iac-matching/SKILL.md) result | The file(s) actually changed, for the rollback note |

## Outputs

| Artifact / field | Result |
|---|---|
| PR title | `finops(<type>): <concise change> [<tier>]` |
| PR body | What/Why/Saving/Risk/Rollback/Verification — see the template and full example below |

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

A fully filled-in example is in [references/worked-example.md](references/worked-example.md).

## Rules

- **T2** findings → open as a **draft** PR and note that user confirmation was given.
- Never present the estimate as realised. Keep basis and confidence visible.
- Include a concrete rollback for any deletion/downsize.
- Link the finding id so the `verify`-mode run and ledger can correlate.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| GitHub pull request best practices | https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests |

### Key takeaways

- A PR body without a rollback step is incomplete, even for a draft — reviewers need it before
  they'll approve a T1/T2 change.
- The verification plan line is what lets the ledger correlate a merged PR back to its eventual
  `verify`-mode record — never omit the finding id.
