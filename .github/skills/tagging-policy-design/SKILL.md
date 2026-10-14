---
name: tagging-policy-design
description: Design a tag taxonomy and Azure Policy enforcement for cost allocation. Use when tag coverage is low or spend cannot be allocated to owners/cost centers.
---

# Tagging policy design

Good tags make cost allocatable. This is a **T0** governance improvement; the saving is usually 0 —
the value is accurate allocation and accountability. Label it honestly.

## Recommended taxonomy (adapt to the org)

| Tag | Purpose | Example |
|---|---|---|
| `env` | lifecycle | dev / test / prod |
| `owner` | accountable person/team | platform-team |
| `costCenter` | chargeback | CC-1001 |
| `application` | workload grouping | payments-api |
| `dataClass` | optional governance | internal / confidential |

## Method

1. Measure coverage per required tag with Resource Graph
   ([resource-graph-kql](../resource-graph-kql/SKILL.md)) and the share of **spend** that is
   unallocatable.
2. Propose the taxonomy, allowed values, and inheritance (RG → resource).
3. Enforce with Azure Policy:
   - `Require a tag on resources` (deny) for critical tags,
   - `Inherit a tag from the resource group` (modify) to backfill,
   - `Audit` first to measure impact before `deny`.

## Pitfalls

- Start with `audit`/`modify`, not `deny` — a hard deny can block deployments on day one.
- Retroactive tags don't reallocate historical cost; they fix it going forward.
- Keep the tag set small and enforced; sprawling optional tags erode consistency.
