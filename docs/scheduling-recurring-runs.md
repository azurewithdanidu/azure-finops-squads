---
title: Recurring FinOps runs
description: Refresh reports safely without bypassing the plugin's approval and privacy gates.
---

## Refresh existing reports

The installed entry skill bundles ledger, KPI and spend-event scripts. A scheduler can run
those offline tools against an explicit consumer run directory. Resolve their installed paths
and use `python -B`; plugin upgrades may change the installation location.

Validate findings before regenerating reports. Keep output under the consumer's ignored
`.finops/` directory. A report refresh does not gather new Azure evidence or prove savings.

## Start new assessments

A new live assessment requires a client that can invoke the plugin and its configured tools.
Do not assume that VS Code, Copilot CLI, Claude Code or Cursor support identical headless
scheduling. Confirm tool availability and the identity's lack of effective write access first.

Only automate read-only discovery, analysis and reporting. Never automatically approve a
finding, invoke remediation, open a PR, merge or deploy. A recurring assessment must stop at
the same human approval boundary as an interactive one.

If unattended read-only identity confirmation cannot be established, use a reminder to launch
the assessment interactively instead.

## Compare runs

The bundled `compare_runs.py` matches findings by type and resource ID. It reports recurring,
new and absent findings. A missing finding is not itself proof of remediation or realised
savings; check the change lifecycle and later cost verification.
