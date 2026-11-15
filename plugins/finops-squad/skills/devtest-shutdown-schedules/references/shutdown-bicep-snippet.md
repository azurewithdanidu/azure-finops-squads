# Shutdown schedule Bicep snippet

AVM-aligned starting point for a single VM's auto-shutdown schedule.

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

Parameterize: `shutdownTime`, `timeZone` (default `AUS Eastern Standard Time`),
`notificationEmail`. For groups of VMs, prefer a Start/Stop automation runbook pattern over
repeating this resource per VM.
