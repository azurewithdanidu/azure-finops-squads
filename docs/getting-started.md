# Getting started

finops-squad runs inside GitHub Copilot (agent mode) in VS Code. This guide gets you from zero to a
first read-only audit.

## 1. Prerequisites

- **VS Code** with GitHub Copilot (agent mode).
- **Node.js** (for the Azure MCP server via `npx`).
- **Python 3.10+** (for `scripts/validate-findings.py` and `scripts/ledger.py`).
- **Azure CLI** (`az`) and an Azure sign-in with at least **Reader**, **Cost Management Reader** and
  **Monitoring Reader** on the target subscription(s).

Install the schema validator dependency:

```bash
pip install jsonschema
```

## 2. Sign in to Azure

```bash
az login
az account set --subscription "<your-subscription>"
```

## 3. Configure MCP servers

Copy the template and restart MCP servers (Command Palette → **MCP: List Servers** → Restart):

```bash
cp .vscode/mcp.json.example .vscode/mcp.json
```

`.vscode/mcp.json` is git-ignored. It contains:

- **azure-mcp** — Microsoft's Azure MCP server (`npx -y @azure/mcp@latest server start`): resource
  access, Monitor metrics, Advisor, optimization, pricing.

Cost querying, Resource Graph, and retail pricing (`arm.query_costs`, `arm.execute_query`,
`arm.get_retail_prices`) are provided directly by this agent host (GitHub Copilot in VS Code) with
**no extra `.vscode/mcp.json` entry needed** — live-verified against a real subscription. An
earlier revision of this guide described a separate, unverified "ARM MCP (CostManagement)" HTTP
server; that was never needed and has been removed. See
[mcp-capability-map.md](./mcp-capability-map.md) for the full correction, and note its one caveat:
this `arm` tool group's availability is host-dependent, not guaranteed on every MCP client.

Budgets, cost forecasting, and commitment/reservation listing are still unavailable from any
backend found so far.

> A third-party community FinOps MCP server was intentionally **not** included — finops-squad uses
> Microsoft servers and host tools only.

## 4. Create your run config

Copy the example to the git-ignored runtime folder:

```bash
mkdir -p .finops
cp docs/config.example.json .finops/config.json
```

Edit `.finops/config.json` with your subscription(s), time window, price basis and IaC repo path.
Never commit this file.

## 5. Run a first audit (read-only)

In Copilot agent mode, use the **run-audit** prompt (`.github/prompts/run-audit.prompt.md`) or ask
the **finops-orchestrator** agent to run an audit. It will:

1. Discover the estate → `inventory.json`, `spend.json`, `advisor.json`.
2. Analyse (waste mode, plus other modes if enabled) → `findings/*.json`.
3. Rank findings → `plan.md`.
4. Visualize → `reports/`.

Then validate:

```bash
python scripts/validate-findings.py .finops/runs/<id>/
```

## 6. Remediate (optional, with confirmation)

Review `plan.md`, approve the findings you want, and let the **finops-implementer** open PRs. It
refuses T3/untiered findings and anything without an IaC match, and opens T2 changes as draft PRs
only after you confirm.

## 7. Verify savings

After PRs merge and a settling period (≥ 7 days, allowing ~3 days of cost-data lag), run the
**verify-savings** prompt. The Analyser (in `verify` mode) records realised savings and the
Visualizer refreshes the ledger.

## Troubleshooting

- **No spend numbers / "spend data unavailable"** — Discovery attempts `arm.query_costs` first;
  this status only appears if that call genuinely failed in your environment (check the recorded
  `reason` in `spend.json`). Waste/utilization findings still work regardless.
- **Validation fails** — run `pip install jsonschema`; the script falls back to minimal checks
  without it.
- **MCP server not listed** — ensure `.vscode/mcp.json` exists and restart MCP servers.
