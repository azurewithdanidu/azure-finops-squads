# Worked example — AVM module reference

Pinned AVM budget module, as it would appear in a `missing-budget` (T0) PR:

```bicep
module budget 'br/public:avm/res/consumption/budget:0.3.3' = {
  name: 'budget-rg-dev'
  params: {
    name: 'rg-dev-monthly'
    amount: 2000
    timeGrain: 'Monthly'
    startDate: '2026-11-01'
    contactEmails: contactEmails
  }
}
```

Checklist before using an AVM module in a PR:

1. Confirm the module exists and the version is real — browse the
   [AVM module index](https://azure.github.io/Azure-Verified-Modules/indexes/bicep/bicep-resource-modules/)
   or use `bicepschema` rather than guessing a version tag.
2. Pin the exact version (`:0.3.3`, not `:latest` or no tag).
3. Pass only the parameters the finding actually needs; don't widen scope by exposing unrelated
   module parameters "just in case".
4. Run `bicep build`/`az bicep lint` mentally against the AVM module's documented required params
   before proposing the PR — a missing required param is the most common AVM authoring mistake.
