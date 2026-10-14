# Security model

finops-squad is designed so that an audit can never damage your Azure estate.

## Read-only against Azure

- Agents use only **Reader**, **Cost Management Reader** and **Monitoring Reader** access.
- No agent is permitted to call a mutating Azure operation — nothing that creates, updates, deletes,
  deallocates, starts, stops or restarts a resource.
- The only agent that writes anything is the **Implementer**, and it writes **files and pull
  requests**, never live Azure resources. It never runs `az`, `terraform apply` or `bicep deploy`.

### How read-only is enforced

Enforcement is layered:

1. **Instruction layer (primary).** The global [copilot-instructions.md](../.github/copilot-instructions.md)
   and every agent definition forbid mutating operations explicitly.
2. **Tool scoping.** Each read-only agent is granted only the Azure MCP namespaces and host tools it
   needs. Note: Azure MCP groups read and write operations under one namespace tool (e.g.
   `compute`), so namespace scoping alone cannot exclude every write subcommand — the instruction
   layer closes that gap.
3. **Human in the loop.** No automated chain reaches the Implementer. The orchestrator stops for
   explicit user confirmation before any remediation, and T2 changes require a second confirmation
   and open as draft PRs.

## PR-only remediation

- All change flows through pull requests to an IaC repository.
- Risk tiers gate what the Implementer may do (see [risk-tiers.md](./risk-tiers.md)). It refuses
  missing or T3 tiers and refuses findings without an `iacMatch.status == found` (producing a
  manual change request for `unmanaged` resources).

## Data handling

- Subscription IDs live only in a **git-ignored** `.finops/config.json`. They are never committed or
  placed in prompts/instructions.
- Run artifacts under `.finops/` are git-ignored by default.
- `.vscode/mcp.json` is git-ignored because it may reference subscription-specific config.
- No secrets in the repo or prompts. Authentication is the user's own Azure sign-in (`az login`);
  credentials stay on the local machine.

## Honest numbers

- Estimates are labelled with a price `basis` (`list-price`/`actual`) and a confidence level.
- A saving is only **realised** after the Analyser (in `verify` mode) confirms it in later cost
  data. The Visualizer and ledger keep estimated and realised savings strictly separate.
