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

## Inputs

| Source | Role |
|---|---|
| `inventory.json` | VM/SQL `licenseType` / edition fields |
| User confirmation (out-of-band) | Licence + Software Assurance entitlement — the squad cannot see this itself |
| `pricing` (retail prices) | License-included vs AHB rate delta |

## Outputs

| Artifact / field | Result |
|---|---|
| `findings/rightsizing.json` entry (tier `T2`) | Estimated saving, confidence capped at medium pending confirmation |

## Method

The full step-by-step is in
[references/ahb-eligibility-checklist.md](references/ahb-eligibility-checklist.md): identify
candidates, verify entitlement as a documented question (not an assumption), price both states,
and write the finding with capped confidence.

## Pitfalls

- **Do not** claim the saving as realised until the user confirms license entitlement — label it an
  estimate with medium/low confidence.
- AHB has dual-use rights windows and per-core/edition rules — document assumptions.
- This is a licensing compliance decision, not just a cost toggle. Keep it recommendation-led.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Azure Hybrid Benefit for Windows Server | https://learn.microsoft.com/en-us/azure/virtual-machines/windows/hybrid-use-benefit-licensing |
| Azure Hybrid Benefit for SQL Server | https://learn.microsoft.com/en-us/azure/azure-sql/azure-hybrid-benefit |
| Software Assurance eligibility | https://learn.microsoft.com/en-us/licensing/docs/licensing/products/windows-server |

### Key takeaways

- Entitlement verification is a question to the user, never an assumption — AHB is the one finding
  type where the squad's own data can't confirm the precondition.
- Keep confidence capped at medium until the user explicitly confirms licences, even if the price
  delta itself is precisely known.
