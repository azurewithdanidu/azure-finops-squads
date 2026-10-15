---
name: tagging-policy-design
description: Design a tag taxonomy and Azure Policy enforcement for cost allocation. Use when tag coverage is low or spend cannot be allocated to owners/cost centers.
---

# Tagging policy design

Good tags make cost allocatable. This is a **T0** governance improvement; the saving is usually 0 —
the value is accurate allocation and accountability. Label it honestly.

## When to use

- Tag coverage is measurably low, or spend can't be allocated to an owner/cost centre.

## Inputs

| Source | Role |
|---|---|
| [resource-graph-kql](../resource-graph-kql/SKILL.md) tag-coverage query | Coverage per required tag |
| `spend.json` | Share of spend that is unallocatable |

## Outputs

| Artifact / field | Result |
|---|---|
| `findings/tagging.json` entry (`type: "tagging-gap"`, tier `T0`) | Taxonomy + policy proposal, coverage numbers |

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
3. Enforce with Azure Policy — `audit` first, then `modify` to backfill, only `deny` once coverage
   is high. A concrete audit/modify/deny rollout sequence is in
   [references/worked-example.md](references/worked-example.md).

## Pitfalls

- Start with `audit`/`modify`, not `deny` — a hard deny can block deployments on day one.
- Retroactive tags don't reallocate historical cost; they fix it going forward.
- Keep the tag set small and enforced; sprawling optional tags erode consistency.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| Azure Policy — tag resources | https://learn.microsoft.com/en-us/azure/governance/policy/samples/built-in-policies#tags |
| Resource naming and tagging decision guide | https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-tagging |
| Policy effects (`audit`/`modify`/`deny`) | https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effects |

### Key takeaways

- `audit` → `modify` → `deny` is the safe rollout order — jumping straight to `deny` is the single
  most common way this finding type backfires.
- The saving is allocation accuracy, not dollars — say so plainly rather than inventing a number.
