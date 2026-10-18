# Manual denominator examples

Example `.finops/config.json` `unitEconomics.denominator` blocks for the `manual-denominator`
method, covering the FinOps Framework's broader
[Unit Economics](https://www.finops.org/framework/capabilities/unit-economics/) definition (cost
per transaction/customer/workload) when no Azure OpenAI token data applies.

## Shape

```json
{
  "unitEconomics": {
    "denominator": {
      "label": "<business unit, plural>",
      "value": <positive number>
    }
  }
}
```

`scripts/kpis.py` divides `spend.json`'s `totalLastMonth` by `value` and labels the result
`<currency>/<label>`. `label` and `value` are both required — a missing or non-positive `value`,
or a missing `label`, falls through to `"method": "unavailable"`.

## Examples

### Per active user (SaaS product)

```json
{ "unitEconomics": { "denominator": { "label": "active users", "value": 12000 } } }
```

Produces e.g. `AUD/active users` — useful when infra cost should scale with monthly active users,
not with a flat total that obscures whether growth or inefficiency is driving spend up.

### Per transaction (e-commerce/payments workload)

```json
{ "unitEconomics": { "denominator": { "label": "transactions", "value": 845000 } } }
```

Useful for a checkout/payments pipeline where the FinOps question is "is cost-per-transaction
improving," not "did total spend go up" (which could just mean more transactions, i.e. more
business).

### Per customer tenant (multi-tenant workload)

```json
{ "unitEconomics": { "denominator": { "label": "customer tenants", "value": 340 } } }
```

Useful when a shared platform's infra is billed as one subscription but needs to be understood as
a per-tenant cost for margin/pricing decisions.

### Per workload/environment (internal platform team)

```json
{ "unitEconomics": { "denominator": { "label": "deployed workloads", "value": 58 } } }
```

Useful for a platform team whose subscription hosts many internal workloads and wants an average
cost-per-workload trend, rather than one opaque subscription total.

## Caveats (apply to every example above)

- The denominator is a **user-supplied claim**, not data the squad independently verifies —
  `scripts/kpis.py`'s note says so every time this method is used.
- It goes stale if the user doesn't update it after a real usage change (e.g. active users
  doubled but the config value wasn't bumped) — a stale denominator produces a misleadingly
  improving or worsening trend. Flag this to the user periodically rather than trusting it forever.
- Never invent a plausible-looking denominator to avoid reporting `"unavailable"` — a wrong
  unit-cost number is worse than an honest gap, per the skill's own rule.
- Don't compare a `manual-denominator` cost-per-unit across runs if the `label`/`value` changed
  between them (e.g. switched from "active users" to "transactions") — that's not a trend, it's
  two different metrics.
