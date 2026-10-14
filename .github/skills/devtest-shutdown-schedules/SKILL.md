---
name: devtest-shutdown-schedules
description: Author Bicep for auto-shutdown and start/stop schedules for dev/test compute. Use when a non-production VM runs 24x7 without a schedule.
---

# Dev/test shutdown schedules

Non-production compute rarely needs to run 24×7. Adding an auto-shutdown schedule is a **T0**
additive change — safe to PR directly.

## When to use

- Dev/test VMs (`env in (dev, test, qa)`) running continuously with low off-hours utilization.

## Savings math

A VM shut down 12h/day on weekdays and all weekend runs ~24% of the hours of 24×7
(≈ 40 of 168 weekly hours). Compute saving = compute_rate × (1 − running_fraction). **Disks and
public IPs still bill while deallocated** — exclude them from the saving.

## Bicep approach (AVM-aligned)

- Prefer `Microsoft.DevTestLab/schedules` (auto-shutdown) for a single VM, or a Start/Stop
  automation pattern for groups.
- Parameterize: `shutdownTime`, `timeZone` (default `AUS Eastern Standard Time`),
  `notificationEmail`.
- Follow [bicep-avm-conventions](../bicep-avm-conventions/SKILL.md). One VM-group schedule per PR.

```bicep
resource shutdown 'Microsoft.DevTestLab/schedules@2018-09-15' = {
  name: 'shutdown-computevm-${vmName}'
  location: location
  properties: {
    status: 'Enabled'
    taskType: 'ComputeVmShutdownTask'
    dailyRecurrence: { time: shutdownTime }
    timeZoneId: timeZone
    targetResourceId: vmId
    notificationSettings: { status: 'Enabled', timeInMinutes: 30, emailRecipient: notificationEmail }
  }
}
```

## Pitfalls

- Auto-start is optional; many teams want manual start. Don't force start schedules.
- Confirm the VM isn't running scheduled off-hours jobs (backups, batch).
- Saving is **compute only** — state that disks/IPs continue to bill.
