# Security model

The human must confirm the active identity has no effective Azure write access at audit scope,
including inherited, group membership and activated eligible roles, before any Azure query. Reader,
Cost Management Reader and Monitoring Reader are appropriate least-privilege roles where needed.
Stop if confirmation is absent; do not probe by attempting a write. Instructions and local
preflight are not independent proof of Azure permissions or human consent.

No Azure mutation, deployment or auto-merge is allowed. Only explicitly approved, risk-gated Bicep
PRs may change IaC. Keep subscription IDs and all private runtime artifacts in an ignored
consumer-workspace `.finops/`, never in the plugin installation.
