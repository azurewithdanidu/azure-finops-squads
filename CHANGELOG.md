# Changelog

All notable changes to **finops-squad** are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Modernised the dashboard UI (presentation only — no data or calculations changed).** Custom
  light/dark theme and minimal toolbar in `.streamlit/config.toml`; a single palette and Altair
  theme in `scripts/dashboard_theme.py` with chart builders in `scripts/dashboard_charts.py`; a
  compact header with currency/price-basis chips; the run selector and persona switch moved from
  the sidebar to a top control row; Material icons on tabs; bordered KPI cards with run-history
  sparklines; consistently labelled and sorted charts, a dashed 90% tagging target and
  text-plus-colour risk tiers; a `column_config` findings table whose row selection opens a
  structured detail dialog; mtime-keyed `st.cache_data` file loading; friendlier empty states. In
  mixed-currency runs the "Estimated saving by type" chart now shows the primary currency only,
  instead of summing across currencies. Minimum Streamlit raised from 1.40 to 1.50. New pure
  helpers and an AppTest smoke test are covered in `tests/test_scripts.py`; the dashboard also
  reads an optional `FINOPS_RUNS_DIR` environment variable.
- **Restructured the agent roster from 10 agents to 5: Orchestrator, Discovery, Analyser,
  Implementer, Visualizer.** The five previous finding agents (Waste Hunter, Rightsizer, Tagger,
  Commitment Planner, Anomaly Detective) plus the Verifier were each thin wrappers around a single
  skill; they are now one `finops-analyser` agent invoked in six modes (`waste`, `rightsizing`,
  `tagging`, `commitment`, `anomaly`, `verify`), each mode loading the same skill as before. Scout
  renamed to Discovery, Fixer renamed to Implementer, Reporter renamed to Visualizer (the
  Visualizer now also points to the dashboard). No skill content changed — they were already
  written mode-agnostic. Updated the Orchestrator's subagent list, all 3 prompts, consolidated
  evals (10 → 5 files, with the Analyser eval covering all 6 modes), and every doc/instruction that
  named the old agents (`docs/architecture.md`, `docs/risk-tiers.md`, `docs/security-model.md`,
  `docs/getting-started.md`, `copilot-instructions.md`, `findings.instructions.md`,
  `bicep.instructions.md`, several skill descriptions, and the README pipeline diagram).

### Fixed

- **Corrected a major capability-map error from v0.1.0.** `cost.query_spend`, `cost.query_aks`,
  and `inventory.list_resources` were marked GAP/partial, assuming a separate, unverified "ARM MCP
  (CostManagement)" HTTP server was required. Live testing against a real subscription showed this
  was wrong: a host-integrated `arm` tool group (`query_costs`, `query_aks_costs`, `execute_query`,
  `get_retail_prices`) is available directly in Copilot/VS Code agent sessions with no extra
  configuration. Spend querying, Resource Graph, and retail pricing are now live-verified working.
  Budgets, forecast, and commitments remain genuine gaps. See `docs/mcp-capability-map.md` for the
  full evidence and the portability caveat (this `arm` tool group's availability is host-dependent).
- Updated the Scout agent, `cost-query-patterns` and `resource-graph-kql` skills, the Reporter and
  Anomaly Detective agents, and related docs/evals to attempt `arm.query_costs` /
  `arm.execute_query` first instead of assuming unavailability.
- Removed the speculative `azure-resource-manager-mcp` HTTP entry from `.vscode/mcp.json.example`.

### Added

- `investigations/<slug>.json` run-artifact convention: agents that investigate a suspected finding
  but find the evidence doesn't hold up now write a preserved "checked, not a finding" record
  instead of forcing or silently dropping it. Documented in `findings.instructions.md`.
- A new corroboration rule in the `idle-compute-detection` skill: never call a network appliance
  (firewall/NAT/VPN/ExpressRoute gateway) idle from a single throughput/bandwidth metric — always
  check a second signal (e.g. rule-hit or connection-count). Added after a live investigation of an
  Azure Firewall nearly produced a false-positive "idle" finding (0 bps average throughput, but
  ~43,000 real network-rule evaluations/day over the same window).

## [0.1.0] - 2026-10-14

First release: the full read-only audit → PR-only remediation → verification loop for Azure,
driven by Copilot custom agents in VS Code.

### Added

- **10 custom agents** (`.github/agents/`): orchestrator, scout, waste-hunter, rightsizer, tagger,
  commitment-planner, anomaly-detective, fixer, verifier, reporter.
- **19 skills** (`.github/skills/`) covering discovery, cost queries, waste/idle/orphan detection,
  rightsizing, tagging, commitments, Bicep/AVM authoring, IaC matching, PR authoring, risk tiering,
  verification and reporting.
- **Global instructions** (`.github/copilot-instructions.md`) plus targeted instructions for Bicep
  (`**/*.bicep`) and run artifacts (`.finops/**`).
- **JSON Schemas** for findings and verifications, with a validation script
  (`scripts/validate-findings.py`) and a savings ledger builder (`scripts/ledger.py`).
- **Fixtures** for offline testing: inventory, spend, advisor, four waste findings and one
  verification.
- **Prompts**: run-audit, verify-savings, quick-waste-scan.
- **Docs**: architecture, MCP tool inventory, MCP capability map, risk tiers, security model,
  getting started, and a config example.
- **Per-agent evaluations** (`evals/`) including Fixer refusal paths.
- **CI** (`.github/workflows/ci.yml`): schema validation + unit tests, Markdown lint, link check.

### Project decisions (v0.1)

- Target user: engineer auditing their **own** subscription(s) (single-tenant).
- IaC scope: **Bicep only** (Terraform deferred).
- Price basis: **require actual rates** where available (PAYG retail counts as actual).
- Currency / locale: **AUD, en-AU**.
- Name / license: **finops-squad**, MIT.

### Backends

- Microsoft **Azure MCP server** + the **Azure Resource Graph** host tool for inventory, compute,
  storage, Advisor, optimization, Monitor metrics and pricing.
- **ARM MCP server (CostManagement toolset)** is the path for spend, budgets, forecast and
  commitments — its endpoint still needs verifying, so those capabilities are degraded/GAP until it
  is connected (see `docs/mcp-capability-map.md`).

### Removed

- The third-party community Azure FinOps MCP server was evaluated and **removed**; finops-squad uses
  Microsoft servers and host tools only.

### Known limitations

- `cost.query_spend`, `cost.forecast`, `budget.list` and `commitments.list` require the ARM MCP
  (CostManagement) server; `cost.query_aks` has no backend yet.
- Azure MCP groups read and write operations per namespace, so read-only is enforced primarily at
  the instruction layer (see `docs/security-model.md`).
- Fixtures cover waste findings; rightsizing/tagging/commitment/anomaly fixtures are not yet
  included.

[0.1.0]: https://github.com/finops-squad/finops-squad/releases/tag/v0.1.0
