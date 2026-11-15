# Worked tiering examples

Concrete calls, kept separate so new cases can be appended without bloating `SKILL.md`.

| Scenario | Tier | Why |
|---|---|---|
| Unattached dev disk, 90d, in IaC | **T1** | Safe delete with rollback; non-production, orphaned |
| Prod VM at 5% CPU | **T3** | Production compute — analysis only, no PR |
| Non-prod VM oversized, owner known | **T2** | Downsize needs confirmation; draft PR |
| Subscription has no budget | **T0** | Purely additive governance change |
| Reservation purchase recommendation | **T3** | Commitment purchases are never a PR |
| Storage lifecycle rule adding `tierToCool`/`tierToArchive` only | **T0** | Additive, non-destructive |
| Storage lifecycle rule that also adds a `delete` action | **T2** | Delete actions are irreversible — needs confirmation |
| Apply Hybrid Benefit to a Windows/SQL VM | **T2** | Depends on licence entitlement the squad can't verify itself |
