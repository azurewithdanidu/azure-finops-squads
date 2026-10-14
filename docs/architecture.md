# Architecture

finops-squad is an IDE-first, multi-agent squad for GitHub Copilot in VS Code. It takes an Azure
estate from "what are we spending?" to "here is the PR that fixes it", then confirms the savings
landed — all read-only against Azure, with every change delivered as a pull request.

## Pipeline

```text
Discover -> Analyse ------------------------------> Rank -> Confirm -> Implement -> Verify -> Visualize
 Discovery  Analyser (waste/rightsizing/tagging/       Orchestrator        Implementer  Analyser   Visualizer
            commitment/anomaly modes)                                                  (verify mode)
```

Agents never call each other directly. They exchange JSON/Markdown artifacts under `.finops/`
(git-ignored). Status transitions (`proposed → approved → pr-open → merged → verified | rejected`)
are owned only by the orchestrator, the Implementer, and the Analyser (in `verify` mode).

## Components

- **Agents** — `.github/agents/*.agent.md` (5 agents: orchestrator, discovery, analyser,
  implementer, visualizer). The Analyser is one agent invoked in six **modes** (`waste`,
  `rightsizing`, `tagging`, `commitment`, `anomaly`, `verify`) rather than one agent per finding
  type — each mode's actual detection method lives in a skill (see below), so the agent file stays
  thin and the domain knowledge stays reusable and swappable. Only the Implementer writes anything,
  and only as a PR.
- **Skills** — `.github/skills/<name>/SKILL.md` (19 skills). Focused how-to knowledge loaded on
  demand — these carry the real detection/method logic for every Analyser mode and were already
  written mode-agnostic, so consolidating the agents required no changes to the skills themselves.
- **Instructions** — `.github/copilot-instructions.md` (global rules) plus targeted
  `.github/instructions/*.instructions.md` (Bicep authoring, `.finops/**` artifacts).
- **Schemas** — `schemas/finding.schema.json`, `schemas/verification.schema.json`.
- **Scripts** — `scripts/validate-findings.py` (schema gate), `scripts/ledger.py` (savings ledger),
  `scripts/dashboard.py` (interactive Streamlit visualizer).
- **Fixtures** — `fixtures/` sample data for offline testing without a live tenant.

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
