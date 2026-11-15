---
name: devtest-shutdown-schedules
description: Analyse dev/test shutdown opportunities and author approved FinOps schedule changes. Use when non-production compute runs continuously. Do not use for generic Bicep writing or live shutdown.
---

# Dev/test shutdown schedules

Load the `finops-squad` skill, follow its preflight and its installed `references/safety-contract.md`.

Non-production compute rarely needs to run 24×7. Adding an auto-shutdown schedule is a **T0**
additive change — safe to PR directly.

## When to use

- Dev/test VMs (`env in (dev, test, qa)`) running continuously with low off-hours utilization.

## Inputs

| Source | Role |
|---|---|
| `inventory.json` + `env` tag | Identifies dev/test VMs in scope |
| `idle-compute-detection` off-hours utilization | Confirms low off-hours usage before proposing |

## Outputs

| Artifact / field | Result |
|---|---|
| `findings/waste.json` entry (`type: "missing-shutdown-schedule"`, tier `T0`) | Proposed schedule + compute-only saving |
| Bicep PR (Implementer) | `Microsoft.DevTestLab/schedules` resource |

## Savings math

A VM shut down 12h/day on weekdays and all weekend runs ~24% of the hours of 24×7
(≈ 40 of 168 weekly hours). Compute saving = compute_rate × (1 − running_fraction). **Disks and
public IPs still bill while deallocated** — exclude them from the saving.

## Method

- Prefer `Microsoft.DevTestLab/schedules` (auto-shutdown) for a single VM, or a Start/Stop
  automation pattern for groups — see the full snippet in
  [references/shutdown-bicep-snippet.md](references/shutdown-bicep-snippet.md).
- Parameterize: `shutdownTime`, `timeZone` (default `AUS Eastern Standard Time`),
  `notificationEmail`.
- Follow `bicep-avm-conventions`. One VM-group schedule per PR.

## Pitfalls

- Auto-start is optional; many teams want manual start. Don't force start schedules.
- Confirm the VM isn't running scheduled off-hours jobs (backups, batch).
- Saving is **compute only** — state that disks/IPs continue to bill.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Auto-shutdown for DevTest Labs VMs | <https://learn.microsoft.com/en-us/azure/lab-services/devtest-lab-auto-shutdown> |
| Start/Stop VMs v2 (automation at scale) | <https://learn.microsoft.com/en-us/azure/azure-functions/start-stop-vms/overview> |
| `Microsoft.DevTestLab/schedules` template reference | <https://learn.microsoft.com/en-us/azure/templates/microsoft.devtestlab/schedules> |

### Key takeaways

- The saving is compute-only — always say so; disks and public IPs keep billing while deallocated.
- Don't assume start schedules are wanted; auto-shutdown alone is the safe default.
