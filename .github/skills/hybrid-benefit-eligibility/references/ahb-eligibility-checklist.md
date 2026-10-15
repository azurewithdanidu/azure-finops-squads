# AHB eligibility checklist

A concrete checklist for turning an AHB candidate into a finding.

1. **Enumerate candidates** — Windows Server VMs / SQL Server VMs / Azure SQL (DB or MI) where
   `licenseType` is not `Windows_Server`, `Windows_Client`, or an AHB-enabled equivalent.
2. **Verify entitlement out-of-band** — the squad cannot see on-prem licensing or Software
   Assurance status. Present this as a documented question for the user:
   - "Do you hold enough Windows Server/SQL Server core licences with active Software Assurance
     (or qualifying subscription) to cover `<N>` cores on `<resource>`?"
3. **Price both states** — compute_rate(license-included) vs compute_rate(AHB, base OS/SQL rate
   only) via `pricing`. The delta is the estimated saving.
4. **Label confidence** — medium at best until the user confirms entitlement; never high.
5. **Write the finding** — `tier: T2`, `iacMatch` per normal rules, saving labelled `list-price` or
   `actual` per [price-basis-handling](../price-basis-handling/SKILL.md), and a note that the
   saving is conditional on confirmed licence entitlement.
