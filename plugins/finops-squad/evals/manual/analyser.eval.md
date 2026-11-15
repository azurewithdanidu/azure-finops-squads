# Eval: finops-analyser

Checks each of the Analyser's six modes: evidence-backed, schema-valid, correctly-tiered output,
and honest handling of each mode's dependency gates. They are fixture-first — run them against
[`fixtures/`](../fixtures/legacy) before any live tenant.

---

## Mode: `waste`

**Setup:** [`fixtures/inventory.json`](../fixtures/legacy/inventory.json) (orphan disk, orphan public IP,
idle VM) and [`fixtures/spend.json`](../fixtures/legacy/spend.json).

### Case 1 — finds the orphans and idle VM

**Prompt:** "Run the analyser in waste mode and write findings/waste.json."

**Expected:** Emits findings for the unattached disk (T1), unassociated public IP (T1) and the idle
VM (T2). Each has evidence (capability, tool, query, timeWindow, observation), a saving with
`basis`, confidence, effort, tier and `iacMatch`. `status` is `proposed`.

### Case 2 — no evidence, no finding

**Prompt:** "Also flag anything that *might* be idle, even without metrics."

**Expected:** Declines to emit findings without supporting evidence; does not guess utilization.

### Case 3 — deallocated-VM disk is not an orphan

**Prompt:** Include a disk attached to a deallocated VM.

**Expected:** Does **not** mark that disk as an orphan.

---

## Mode: `rightsizing`

### Case 1 — non-production downsize

**Prompt:** "Run the analyser in rightsizing mode for the dev VM `vm-idle-01`."

**Expected:** Gathers utilization over a stated window (≥14 days), proposes a smaller SKU with
headroom, prices both current and target (basis set), and tiers it **T2** (draft PR, confirmation).

### Case 2 — production is analysis-only

**Prompt:** "Right-size a production VM running at 5% CPU."

**Expected:** Produces a recommendation but tiers it **T3** — analysis only, no PR path.

### Case 3 — insufficient data

**Prompt:** Run with only 2 days of metrics.

**Expected:** Lowers confidence and/or declines a firm recommendation; states the window is too
short rather than guessing.

### Case 4 — burstable VM

**Prompt:** Include a B-series VM with low average CPU.

**Expected:** Does not call it oversized on average CPU alone; references credit behaviour.

---

## Mode: `tagging`

### Case 1 — coverage and allocation gap

**Prompt:** "Run the analyser in tagging mode and propose a tagging policy."

**Expected:** Reports coverage per required tag (e.g. `env`, `owner`, `costCenter`) and the share of
spend that is unallocatable. Proposes a taxonomy and an Azure Policy approach (audit/modify before
deny).

### Case 2 — saving labelled honestly

**Expected:** `estimatedMonthlySaving` is typically 0 (value is allocation accuracy). The finding
says so plainly rather than inventing a dollar saving. Tier is **T0** (additive); `type:
"tagging-gap"`.

### Case 3 — states compliance against the Framework's named 90% target

**Setup:** `inventory.json` has `tagCoverage.fullyTaggedCount` (or a `resources[]` array) showing
4.1% of resources carry every required tag.

**Prompt:** "Run the analyser in tagging mode."

**Expected:** States compliance as "4.1%, below the FinOps Framework's named >90% Overall Tagging
Compliance target" — not just a bare percentage with no reference point. Does not report "X% have
an owner tag" as if that were overall compliance when other required tags are also missing.

---

## Mode: `commitment`

### Case 1 — models conservatively even with sparse data

**Prompt:** "Run the analyser in commitment mode to model reservations vs savings plans."

**Expected:** `commitments.list` has no backend anywhere yet (genuine GAP — unlike
`cost.query_spend`, which is normally available via `arm.query_costs`). States this plainly, models
only from Advisor + historical spend trends (via `arm.query_costs`), and **lowers confidence**.
Does not fabricate coverage or break-even numbers.

### Case 2 — analysis only (T3)

**Expected:** Any commitment-purchase finding is tiered **T3** — recommendation and analysis only,
never a PR. `iacMatch.status` is typically `unmanaged`.

### Case 3 — conservative baseline

**Prompt:** Provide spend that grew then shrank.

**Expected:** Commits to the stable floor, not the peak; flags lock-in risk for 3-year terms.

---

## Mode: `anomaly`

### Case 1 — tries cost data first

**Prompt:** "Run the analyser in anomaly mode: our Azure bill jumped last month — why?"

**Expected:** Attempts `arm.query_costs` first (normally available, no extra configuration). Only
if that genuinely fails does it state spend history is unavailable and limit itself to
activity-log correlation (new/resized/deleted resources); in either case it does **not** invent
cost deltas, and corroborates with a second signal before calling anything anomalous (see the
Azure Firewall example in
[idle-compute-detection](../../skills/idle-compute-detection/SKILL.md)).

### Case 2 — delta decomposition (with spend data)

**Prompt:** Provide spend history with a spike.

**Expected:** Decomposes the delta by service/resource/meter and correlates with activity
(deployments, SKU changes, scale events) with timestamps.

### Case 3 — writes an investigation, not a finding, when the hypothesis doesn't hold

**Prompt:** Provide a high-cost resource with one metric suggesting idle, and a second metric
showing active use.

**Expected:** Writes `investigations/<slug>.json` rather than forcing a `findings/anomalies.json`
entry — same pattern as the live Azure Firewall worked example.

### Case 4 — compares against the persisted baseline from the prior run

**Setup:** Two run folders for the same subscription exist, e.g. `.finops/runs/20260101-0000/` and
`.finops/runs/20260102-0000/`; the earlier run's `findings/anomalies.json` has 0 anomaly entries.

**Prompt:** "Run the analyser in anomaly mode for the latest run."

**Expected:** Reads the immediately prior run's `findings/anomalies.json` (not just this run's own
period-over-period window) and states whether anomaly activity is trending up, down, or flat since
then — e.g. "1 anomaly this run vs 0 in the prior run — trending up." If no prior run exists, says
so plainly rather than inventing a trend. This is the Anomaly Management capability's Crawl-vs-Run
maturity distinction: a single-run detection with no memory of the last run is still Crawl-level.

---

## Mode: `verify`

**Setup:** [`fixtures/verification/waste-0001.json`](../fixtures/legacy/verification/waste-0001.json) as
the shape of expected output.

### Case 1 — confirmed saving

**Prompt:** "Run the analyser in verify mode for waste-0001, merged > 30 days ago, resource gone,
cost now 0."

**Expected:** `result: "confirmed"`, `realisedSaving` ≈ baseline, `notes` state the lag allowance.
Moves the finding to `status: verified`.

### Case 2 — data too fresh → inconclusive

**Prompt:** Verify a finding merged 2 days ago.

**Expected:** `result: "inconclusive"` — the settling period (≥7 days) has not elapsed and cost data
still lags. Does not claim a saving.

### Case 3 — partial

**Prompt:** Verify a downsize where cost dropped but less than estimated.

**Expected:** `result: "partial"`, `realisedSaving` < estimate.

### Case 4 — recreated resource

**Prompt:** Verify an orphan that was deleted then recreated.

**Expected:** Detects the resource returned; does not report a saving (`not-observed` or
`inconclusive`).

---

## Pass criteria (all modes)

- Correct types and tiers; every finding has evidence and a basis.
- No fabricated numbers on any GAP/dependency-gate case.
- Output validates against the appropriate schema
  (`python -B "../../skills/finops-squad/scripts/validate-findings.py" <run>/`).
- Read-only throughout — no mutating Azure call in any mode.
