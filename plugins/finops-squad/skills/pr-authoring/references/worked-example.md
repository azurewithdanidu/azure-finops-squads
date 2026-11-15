# Worked example — full PR body

Title: `finops(orphaned-disk): remove unattached disk-orphan-01 [T1]`

```markdown
## What
Remove the unattached managed disk `disk-orphan-01` in `rg-dev`.

## Why (evidence)
- Finding: `waste-0001` (orphaned-disk, tier T1)
- Observation: diskState=Unattached for 105 days; no attach activity-log events in the window
- Source: arm.execute_query — `Resources | where type == 'microsoft.compute/disks' | where properties.diskState == 'Unattached'` over 2026-09-15/2026-10-14

## Estimated saving
- **31.10 AUD/month** (basis: actual, confidence: high)

## Risk & tier
- Tier T1: safe delete of an orphaned, non-production resource with evidence
- Blast radius: `modules/disks/dev.bicep` only — no other resource references this disk

## Rollback
- Revert this PR, or re-add the `disks[2]` array entry in `modules/disks/dev.bicep` and
  `dev.bicepparam` and redeploy — the disk is not recoverable once deleted, so rollback restores
  the *declaration*, not prior data.

## Verification plan
- After merge + settling period (≥7d, allow ~3d cost lag), the Analyser (in `verify` mode)
  re-checks the cost slice for `disk-orphan-01` and records `verification/waste-0001.json`.
```
