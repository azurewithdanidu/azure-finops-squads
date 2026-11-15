# Worked example — executive summary excerpt

```markdown
## Spend overview (Sep 2026 – AUD)
Total spend: $48,210 (currency as returned by the API: AUD — matches report default)

## Savings opportunity
- Estimated monthly saving identified: **$1,840** (5 findings, confidence: 3 high / 2 medium)
- Realised monthly saving to date: **$412** (2 findings verified `confirmed`)

## Headline findings
1. `waste-0003` idle-vm (T2) — $165.40/month estimate, high confidence — pending confirmation
2. `tagging-0001` tagging-gap (T0) — allocation accuracy, not a dollar saving
3. `waste-0001` orphaned-disk (T1) — $31.10/month — **verified, confirmed**

## Status
3 proposed, 1 approved, 1 pr-open, 2 merged, 2 verified, 0 rejected
```

Note the discipline: **estimated** and **realised** totals are never merged into one number, the
spend currency is stated explicitly even though it happens to match here, and `tagging-0001`'s
zero-dollar saving is shown honestly rather than omitted or inflated.
