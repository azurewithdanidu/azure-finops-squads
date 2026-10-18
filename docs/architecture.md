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

`scripts/dashboard.py` loads the selected run once into a `RunContext` (`scripts/dashboard_ui.py`)
and hands it to one of two renderers, chosen by the persona control or `?view=executive|engineering`
(with `&run=<run id>`; both are synced with `st.query_params`, and invalid values fall back to
Engineering and the newest run). The Executive view reflects the FinOps Framework's Leadership
persona; the Engineering view its practitioner persona.

- **Executive** (`scripts/dashboard_exec.py`) is one page with no raw tables: the headline sentence,
  four KPI cards, top 5 cost drivers, "decisions needed" cards, goal progress bars, a collapsed
  reliability note and the run's `executive-summary.md`. It omits finding ids, tier codes, IaC
  match, resource ids, status funnels, run-comparison tables and raw JSON.
- **Engineering** (`scripts/dashboard_eng.py`) has four tabs: **Work queue** (action-bucket filter,
  findings table, row-selection detail dialog with evidence, Azure Portal link and a rule-based
  blocker/next step), **Spend** (by service and resource group, source caveats), **Governance**
  (tag coverage per required tag, iteration goals, findings overview) and **History & data
  quality** (KPI cards and notes, trend, run comparison, `run-status.md`, per-run artifact
  checklist).

Every finding sits in exactly one **action bucket**, assigned by `classify_finding` in
`scripts/dashboard_helpers.py` (first match wins): status approved / pr-open / merged → *In flight*;
status verified / rejected, or type `anomaly` → *Informational*; tier T3 or missing (the Implementer
refuses these) → *Decision needed*; `iacMatch.status == found` → *Ready for PR*; anything else →
*Blocked on IaC*. `TYPE_LABELS` gives each finding type a plain-English name.

The numbers both views show come from the same pure helpers, so they cannot disagree:
`dashboard_helpers.py` (buckets, labels, `md_escape`, `safe_url`, `run_fingerprint`) and
`scripts/dashboard_insights.py` (`bucket_totals`, `build_headline`, `reliability_notes`,
`goal_progress`, `blocker_and_next_step`, `tag_coverage_rows`, …). Savings are always grouped per
currency and never added across currencies; estimated and realised stay separate. Presentation is
split into `.streamlit/config.toml` (native light/dark theme, minimal toolbar; no custom CSS),
`scripts/dashboard_theme.py` (design tokens, Altair theme) and `scripts/dashboard_charts.py` (chart
builders). The `st.cache_data` loaders are keyed on each artifact's mtime. Artifact text (resource
names, summaries, tags, the Markdown reports) is untrusted: it is rendered through native
components only, never raw HTML, and Markdown-escaped first.

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
