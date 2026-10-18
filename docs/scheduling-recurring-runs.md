# Scheduling recurring finops-squad runs

finops-squad is **IDE-first** — a run is normally started by asking the orchestrator in Copilot
agent mode (see [getting-started.md](./getting-started.md)). The Microsoft FinOps Toolkit's own
[FinOps alerts](https://microsoft.github.io/finops-toolkit/alerts) tool runs on "a fully
configurable schedule, continuously scanning your selected subscriptions for idle resources" —
this doc gives finops-squad an equivalent recipe, split into what's safely automatable today and
what still needs a human in the loop.

## The non-negotiable boundary

Per [copilot-instructions.md](../.github/copilot-instructions.md) principle 5 — **"Human in the
loop... no fully automatic chains that reach the Implementer without a person approving"** — a
recurring schedule may automate **Discovery → Analyse → Rank** (all strictly read-only), but it
must **never** auto-confirm findings or auto-invoke the Implementer. Scheduling makes the
*assessment* recur; it does not — and must not — make remediation automatic.

## Part 1 — Fully automatable today: keep reports fresh for the latest run

`scripts/ledger.py`, `scripts/kpis.py`, and `scripts/validate-findings.py` are plain Python with no
agent/Azure dependency once a run folder already has `findings/*.json` — they're genuinely
cron/Task-Scheduler-safe as-is. A useful recurring job: re-validate and regenerate reports for
whichever run is newest, and flag threshold breaches (e.g. tagging compliance dropping below the
Framework's 90% target, or an anomaly count trending up) without opening the dashboard manually.

### Linux / macOS (cron)

```bash
# crontab -e
# Every day at 07:00, refresh reports for the most recent run and flag regressions.
0 7 * * * cd /path/to/azure-finops-squads && ./scripts/refresh-latest-run.sh >> /tmp/finops-squad-refresh.log 2>&1
```

```bash
#!/usr/bin/env bash
# scripts/refresh-latest-run.sh (example — not shipped; adapt and save it yourself)
set -euo pipefail
LATEST_RUN=$(ls -1 .finops/runs | sort | tail -n 1)
RUN_DIR=".finops/runs/${LATEST_RUN}"

python scripts/validate-findings.py "${RUN_DIR}/"
python scripts/ledger.py "${RUN_DIR}/"
python scripts/kpis.py "${RUN_DIR}/" --runs-dir .finops/runs

# Example threshold check — adapt the jq path/threshold to your own alerting (email, Slack, etc.)
COMPLIANCE=$(jq -r '.kpis.taggingCompliance.value // "null"' "${RUN_DIR}/reports/kpis.json")
if [ "${COMPLIANCE}" != "null" ] && (( $(echo "${COMPLIANCE} < 90" | bc -l) )); then
  echo "⚠️ Tagging compliance ${COMPLIANCE}% is below the FinOps Framework's 90% target (run ${LATEST_RUN})"
fi
```

### Windows (Task Scheduler)

Create a scheduled task with:

- **Program/script**: `powershell.exe`
- **Arguments**: `-NoProfile -ExecutionPolicy Bypass -File "D:\path\to\azure-finops-squads\scripts\refresh-latest-run.ps1"`
- **Trigger**: Daily, e.g. 07:00

```powershell
# scripts/refresh-latest-run.ps1 (example — not shipped; adapt and save it yourself)
Set-Location 'D:\path\to\azure-finops-squads'
$latestRun = (Get-ChildItem .finops\runs -Directory | Sort-Object Name | Select-Object -Last 1).Name
$runDir = ".finops\runs\$latestRun"

python scripts/validate-findings.py "$runDir/"
python scripts/ledger.py "$runDir/"
python scripts/kpis.py "$runDir/" --runs-dir .finops/runs

$kpis = Get-Content "$runDir\reports\kpis.json" | ConvertFrom-Json
$compliance = $kpis.kpis.taggingCompliance.value
if ($null -ne $compliance -and $compliance -lt 90) {
    Write-Output "Tagging compliance $compliance% is below the FinOps Framework's 90% target (run $latestRun)"
}
```

Both examples are illustrative starting points — wire the threshold check into whatever
notification channel you already use (email, Teams, Slack webhook); this repo doesn't ship a
notification integration.

## Part 2 — Triggering a new read-only assessment on a schedule

Starting a genuinely **new** Discovery → Analyse → Rank cycle on a timer (rather than just
refreshing reports for an existing run) requires something that can drive the Copilot agent
non-interactively — this repo does not assume or ship such an integration, since finops-squad's
architecture is deliberately IDE-first (see [architecture.md](./architecture.md)). If your
environment has one of the following available, the same "read-only only" rule still applies:

- **GitHub Copilot CLI**, if installed and authenticated in your environment, can run an agent
  prompt non-interactively. Point it at the **run-audit** prompt
  (`.github/prompts/run-audit.prompt.md`) on a cron/Task Scheduler trigger identical to Part 1's,
  but **stop here** — do not chain the output into anything that approves findings or invokes the
  Implementer automatically. Treat the scheduled run exactly like a manually-triggered one: it
  produces `plan.md` and stops at the confirmation gate for a human to review.
- **GitHub Actions** (`schedule:` trigger) assigned to the GitHub Copilot coding agent, if your
  organization has that entitlement, can open a PR containing a fresh run's artifacts for human
  review — again, never auto-merging or auto-confirming remediation.

If neither is available in your environment, the lowest-friction option is simply a recurring
calendar reminder to run the orchestrator yourself in VS Code — which is also the only option that
requires zero new infrastructure and is guaranteed to respect the confirmation gate, since a human
is literally running it.

## What this does *not* change

- The orchestrator's [iteration-brief](../.github/skills/iteration-brief/SKILL.md) still defines
  the measurement window for a multi-run iteration — scheduling how *often* a run happens doesn't
  replace stating *why* it's happening.
- `scripts/dashboard.py`'s cross-run comparison and KPI trend panel already assume multiple runs
  accumulate over time in `.finops/runs/` — a recurring schedule (of either kind above) is what
  actually populates that trend with real data instead of a single point.

---

## References

### Microsoft / Azure documentation

| Topic | Link |
|---|---|
| FinOps alerts (the Toolkit's own scheduled-scan tool) | https://microsoft.github.io/finops-toolkit/alerts |
| GitHub Actions `schedule` trigger | https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule |
| Windows Task Scheduler | https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-start-page |
| cron(5) | https://man7.org/linux/man-pages/man5/crontab.5.html |

### Key takeaways

- Refreshing reports for an existing run is 100% script-only and safe to automate today — no
  agent, no Azure call, no approval risk.
- Triggering a brand-new assessment on a schedule needs *something* that can drive the agent
  non-interactively; this repo doesn't assume you have that, and documents it as optional.
- No schedule, however configured, is allowed to shorten the distance to the Implementer — the
  confirmation gate is identical whether a run was started by a human or a timer.
