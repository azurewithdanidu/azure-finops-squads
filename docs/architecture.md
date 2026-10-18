# Architecture

finops-squad is an IDE-first, multi-agent squad for GitHub Copilot in VS Code. It takes an Azure
estate from "what are we spending?" to "here is the PR that fixes it", then confirms the savings
landed — all read-only against Azure, with every change delivered as a pull request.

## Pipeline

```text
Discover -> Analyse (parallel) --------------------> Rank -> Confirm -> Implement -> Verify -> Visualize
 Discovery  Analyser (waste/rightsizing/tagging/       Orchestrator        Implementer  Analyser   Visualizer
            commitment/anomaly modes, run concurrently)                                (verify mode)
```

Agents never call each other directly. They exchange JSON/Markdown artifacts under `.finops/`
(git-ignored). Status transitions (`proposed → approved → pr-open → merged → verified | rejected`)
are owned only by the orchestrator, the Implementer, and the Analyser (in `verify` mode).

The orchestrator also maintains a live `run-status.md` dashboard per run (see
[run-orchestration](../.github/skills/run-orchestration/SKILL.md)) — a lightweight phase table with
a status legend, separate from the ranked detail in `plan.md`, so a run can be checked or resumed
without replaying the chat history. The five independent Analyser modes (`waste`, `rightsizing`,
`tagging`, `commitment`, `anomaly`) are **invoked as concurrent sessions** in a single batched turn
rather than one after another — they all depend only on Discovery's artifacts, never on each
other — with each mode writing only its own `findings/<mode>.json` file and its own dashboard row
(see [phase-delegation](../.github/skills/phase-delegation/SKILL.md)). A failed phase/mode is
retried up to twice with the exact failing assertion restated before the orchestrator stops and
records a blocker; retries never reach the Implementer automatically — the confirmation gate still
applies every time. To resume an interrupted run, the orchestrator re-verifies every artifact
claimed complete and continues from the earliest one that fails re-verification, not from the
latest claimed status.

A run can optionally serve a stated FinOps iteration goal rather than just producing a one-off
finding list — see [iteration-brief](../.github/skills/iteration-brief/SKILL.md). The orchestrator
captures a bounded, measurable brief (1-3 goals, a baseline, a target, a measurement window,
business guardrails) in `.finops/runs/<id>/iteration.md` + `iteration.json`, lets it inform *why*
something is prioritized without inventing a single blended "business value" score, and hands it to
the Visualizer for a `reports/retrospective.md` at close-out. **This is entirely optional** — a
plain one-off scan behaves identically whether or not a brief exists.

## Components

- **Agents** — `.github/agents/*.agent.md` (5 agents: orchestrator, discovery, analyser,
  implementer, visualizer). The Analyser is one agent invoked in six **modes** (`waste`,
  `rightsizing`, `tagging`, `commitment`, `anomaly`, `verify`) rather than one agent per finding
  type — each mode's actual detection method lives in a skill (see below), so the agent file stays
  thin and the domain knowledge stays reusable and swappable. Only the Implementer writes anything,
  and only as a PR.
- **Skills** — `.github/skills/<name>/SKILL.md` (22 skills). Focused how-to knowledge loaded on
  demand. Most carry the real detection/method logic for an Analyser mode or Implementer step, and
  were already written mode-agnostic, so consolidating the agents required no changes to them. Two
  are orchestration-support skills used by the orchestrator itself: `run-orchestration` (the
  `run-status.md` dashboard, ownership/merge rules, resume procedure) and `phase-delegation` (the
  per-phase invocation contract, artifact/minimum-content checks, and the bounded retry procedure).
  A third, `iteration-brief`, is the optional FinOps-iteration contract described above.
  Every skill follows the shape in [skill-authoring-guide.md](./skill-authoring-guide.md): a
  concise `SKILL.md` (Purpose/When to use/Inputs/Outputs/Method/Rules-Pitfalls, closing with a
  doc-link and key-takeaways `## References` section) plus a `references/` folder holding anything
  long, example-shaped, or reusable from elsewhere — query catalogs, Bicep/JSON snippets,
  parameter tables, worked examples. Repo-wide shared contracts (`schemas/*.json`,
  `scripts/*.py`) are never moved into a skill's `references/` folder — only linked.
- **Instructions** — `.github/copilot-instructions.md` (global rules) plus targeted
  `.github/instructions/*.instructions.md` (Bicep authoring, `.finops/**` artifacts).
- **Schemas** — `schemas/finding.schema.json`, `schemas/verification.schema.json`.
- **Scripts** — `scripts/validate-findings.py` (schema gate), `scripts/ledger.py` (savings ledger,
  grouped by currency — see Honest numbers below), `scripts/kpis.py` (named FinOps KPI set — see
  below), `scripts/dashboard.py` (interactive Streamlit visualizer, organized into named tabs; its
  pure/IO logic lives in `scripts/dashboard_helpers.py` so it's unit-testable without a Streamlit
  runtime — see `tests/test_scripts.py`).
- **Fixtures** — `fixtures/` sample data for offline testing without a live tenant;
  `tests/fixtures/mixed_currency/` specifically exercises the never-blend-currencies rule.

## Named KPIs (FinOps Foundation alignment)

Per the FinOps Framework's [KPIs & Benchmarking](https://www.finops.org/framework/capabilities/kpis-benchmarking/)
capability ("a curated, well-documented set of KPIs... regularly reviewed for relevance" — not raw,
unnamed totals), `scripts/kpis.py` computes a small, named set into `reports/kpis.json`:

| KPI | Source capability | Honesty rule |
|---|---|---|
| `taggingCompliance` | Reporting & Analytics' named >90% target | `method: "unavailable"` with a `note`, never guessed, when `inventory.json` lacks tag data |
| `allocationCoverage` | Reporting & Analytics' allocated/unallocated spend output | Same — needs both a spend breakdown and resource-group tags |
| `estimatedSavingsOpportunity` | Reuses `scripts/ledger.py`'s primary-currency total | Notes explicitly when the run is mixed-currency |
| `realisedSavingsRate` | realised ÷ estimated, as a % | A true `0%` (not "unavailable") when nothing is estimated yet |
| `anomalyCount` | Anomaly Management's maturity bar (persisted baseline, not single-run detection) | `trend: "unavailable"` with no earlier run to compare against |

`scripts/dashboard.py`'s **📈 KPIs & Trends** tab renders these as metric cards plus a run-over-run
trend chart (`dashboard_helpers.kpi_trend_dataframe`), alongside the cross-run comparison described
below. `.finops/config.json`'s optional `tagging.requiredTags` controls which tags count toward
compliance (default `owner`/`environment`/`application`, with `env`/`environment` treated as
synonyms to match the published taxonomy in
[tagging-policy-design](../.github/skills/tagging-policy-design/SKILL.md)).

## Dashboard structure and personas

`scripts/dashboard.py` is organized into three named tabs, mirroring the Microsoft FinOps Toolkit's
own Power BI report structure rather than one long flat page: **Cost Summary** (headline KPIs,
spend, estimated-vs-realised), **Waste & Governance** (iteration progress, savings-by-type,
tier/status funnels, the findings table with a row-selection detail dialog), and **KPIs & Trends**
(the named KPI set above as cards with sparklines, its trend across runs, and the cross-run
comparison). A persona switch (Engineering / Leadership) in the top control row reflects the
Framework's own guidance that different personas need different levels of detail — Leadership
sees KPI cards and charts only; Engineering additionally sees the findings table and per-finding
evidence.

Presentation is split so most of it is testable without a Streamlit runtime:

- `.streamlit/config.toml` — the native light/dark theme and minimal toolbar. No custom CSS is used.
- `scripts/dashboard_theme.py` — design tokens (categorical, semantic and tier colours, chart
  sizes) and the registered Altair theme.
- `scripts/dashboard_charts.py` — chart builders that share one height, direct value labels and
  compact numbers.
- `scripts/dashboard_helpers.py` — pure helpers, including `md_escape` and `safe_url` for
  untrusted artifact text, and `run_fingerprint`, which keys the `st.cache_data` loaders on each
  file's mtime so reruns don't re-read every artifact.

Artifact text (resource names, summaries, tags) is untrusted: the dashboard renders it through
native components only, never raw HTML, and Markdown-escapes it first.

## Honest numbers: currency safety

`scripts/ledger.py` groups every total by currency — it never sums `estimatedMonthlySaving` or
`realisedSaving` across differing currencies into one blended number. The top-level
`ledger["currency"]`/`["totals"]`/`["byType"]` reflect only the currency with the most findings
(for backward compatibility with single-currency runs); `ledger["mixedCurrencies"]` is `true`
whenever more than one currency is present, and `ledger["byCurrency"]` carries every currency's own
totals. `scripts/dashboard.py` checks `mixedCurrencies` and shows a per-currency breakdown instead
of a misleading single total whenever it's set. The dashboard also supports comparing two runs
(matching findings by `type` + `resourceId`, not by the per-run `id`) to show what's resolved,
recurring, or new since an earlier assessment — see `compare_runs` in
`scripts/dashboard_helpers.py`. See [scheduling-recurring-runs.md](./scheduling-recurring-runs.md)
for how to keep multiple runs accumulating so these trend/comparison views have real data.

## Capability contract

Agents reason about **capabilities**, not tool names. The capability → real-tool mapping lives in
[mcp-capability-map.md](./mcp-capability-map.md), and the full tool inventory in
[mcp-tool-inventory.md](./mcp-tool-inventory.md). Swapping a backing server only changes that map,
not the agents.

## MCP backends (all Microsoft)

- **Azure MCP server** (`@azure/mcp`): inventory, compute/storage, Advisor, optimization, Monitor
  metrics, pricing. Installed via `.vscode/mcp.json`.
- **Host-integrated `arm` tool group**: spend (`query_costs`), AKS cost (`query_aks_costs`),
  Resource Graph KQL (`execute_query`/`generate_query`/`validate_query`), and retail pricing
  (`get_retail_prices`) — **live-verified** against a real subscription with **no extra
  configuration**. Provided directly by the agent host (GitHub Copilot in VS Code), not by the
  `@azure/mcp` npm package. Budgets, forecast, and commitments have no backend here either — still
  a GAP. See [mcp-capability-map.md](./mcp-capability-map.md) for the full correction and the
  portability caveat (this tool group may not be present in every MCP client).
- The host tool `azure_query_azure_resource_graph` (an alternative KQL path) returned a
  "not registered" error in testing — prefer `arm.execute_query`.

> A third-party community FinOps MCP server was evaluated and **removed** — the squad uses
> Microsoft servers and host tools only.

## Read-only enforcement — note on tool granularity

The Azure MCP server groups tools by namespace (e.g. `compute` covers both `get` and
`create/delete/power-state`). Because tool grants are per-namespace, read-only is enforced
primarily at the **instruction layer**: the global instructions and every agent forbid calling any
mutating operation, and only the Implementer may edit files / open PRs (never deploy). See
[security-model.md](./security-model.md).

## v0.1 decisions

- Target user: engineer auditing their **own** subscription(s) (single-tenant).
- IaC scope: **Bicep only** (Terraform deferred).
- Price basis: **require actual rates** where available; PAYG retail counts as actual.
- Currency/locale: **AUD, en-AU**.
- Name/license: **finops-squad**, MIT.
