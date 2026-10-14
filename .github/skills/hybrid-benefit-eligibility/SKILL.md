---
name: hybrid-benefit-eligibility
description: Check and document Azure Hybrid Benefit eligibility for Windows Server and SQL Server to cut licensing cost. Use when VMs/SQL run without AHB applied.
---

# Azure Hybrid Benefit (AHB) eligibility

AHB lets you apply existing on-prem licenses with Software Assurance to Azure, removing the license
portion of the rate. Applying AHB is a config change on the resource — usually **T2** (needs
confirmation that licenses exist) and **analysis-first** because it depends on licensing you must
verify out-of-band.

## When to use

- Windows Server VMs billed at full (license-included) rate.
- SQL Server VMs / Azure SQL (DB/MI) without AHB.

## Method

1. Identify candidates: Windows/SQL resources where `licenseType` is not `Windows_Server` /
   `Windows_Client` / AHB-enabled.
2. **Verify entitlement**: enough licenses with active Software Assurance. The squad cannot see your
   licensing — present this as a documented check for the user to confirm.
3. Estimate the saving = compute_rate(license-included) − compute_rate(AHB) via `pricing`.

## Pitfalls

- **Do not** claim the saving as realised until the user confirms license entitlement — label it an
  estimate with medium/low confidence.
- AHB has dual-use rights windows and per-core/edition rules — document assumptions.
- This is a licensing compliance decision, not just a cost toggle. Keep it recommendation-led.
