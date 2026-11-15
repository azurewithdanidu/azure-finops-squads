---
title: FinOps research
description: Historical research on FinOps capabilities and opportunities for finops-squad.
---

## FinOps research: what FinOps actually is, and where finops-squad can grow

> Historical research: dashboard-specific observations and proposals below predate removal of the
> interactive dashboard and do not describe the current product.

Research-only analysis (no code changes resulted from this document). Grounded in live research
against primary sources — not assumed or inferred:

- [FinOps Foundation Framework](https://www.finops.org/framework/) — Principles, Personas,
  Domains/Capabilities, Maturity Model
- Capability deep-dives: [Anomaly Management](https://www.finops.org/framework/capabilities/anomaly-management/),
  [Reporting & Analytics](https://www.finops.org/framework/capabilities/reporting-analytics/),
  [KPIs & Benchmarking](https://www.finops.org/framework/capabilities/kpis-benchmarking/),
  [Allocation](https://www.finops.org/framework/capabilities/allocation/),
  [Unit Economics](https://www.finops.org/framework/capabilities/unit-economics/)
- [FinOps Maturity Model](https://www.finops.org/framework/maturity-model/) (Crawl/Walk/Run)
- [Microsoft FinOps Toolkit](https://microsoft.github.io/finops-toolkit/) — Power BI reports,
  FinOps hubs, Optimization Engine, FinOps alerts
- [FOCUS spec](https://focus.finops.org/)

## 1. What FinOps actually is (grounded, not assumed)

FinOps is **not** "find and fix cloud waste." The Foundation defines it as a discipline with:

- **Principles** (e.g. "everyone takes ownership for their technology usage," "decisions are
  driven by business value")
- **Core personas** who are *always* engaged: FinOps Practitioner, Engineering, Finance,
  Leadership, Procurement, Product (+ Allied personas)
- **Domains**, each with **Capabilities** underneath — the current Framework is organized as
  three domains:
  - **Understand Usage & Cost**: Data Ingestion, Allocation, Reporting & Analytics, Anomaly
    Management, Planning & Estimating, Forecasting, Budgeting, KPIs & Benchmarking, Unit Economics
  - **Optimize Usage & Cost**: Architecting for Workload Placement, Usage Optimization, Rate
    Optimization, Licensing & SaaS, Sustainability
  - **Quantify/Manage**: Executive Stakeholder Alignment, FinOps Practice Operations,
    Governance/Policy/Risk, FinOps Education & Enablement, FinOps Assessment, Automation &
    Tools/Services, Intersecting Disciplines
- A **Crawl/Walk/Run maturity model** applied *per capability*, not just once for the whole org
- **FOCUS** — a vendor-neutral billing schema (our own "FOCUS-aligned terminology ≠ FOCUS-format
  data" distinction, already documented in `finops-reporting/SKILL.md`, is exactly correct per the
  spec's own framing)

**Where finops-squad sits today:** it covers slices of **Anomaly Management**,
**Reporting & Analytics** (partially), and pieces of **Optimize Usage & Cost** (rightsizing, orphan
cleanup = Usage Optimization; commitment modelling = Rate Optimization). It does **not** currently
touch Allocation depth, Unit Economics, Forecasting, Budgeting, Planning & Estimating,
Licensing & SaaS, or any Governance/Policy capability beyond basic tagging.

## 2. Concrete, cited gaps and opportunities

### A. Anomaly Management — our weakest-matched capability vs. the Framework's own maturity bar

The Framework's **Crawl** level is explicitly: *"Manually checking for anomalous spending using
reporting... reacting more than a week after it occurs... anomaly alerts sent to a central team, or
require manual action."* **Run** level requires: *"mature anomaly detection tooling embedded across
the organization, automation to detect/suggest-resolution/resolve, alerts integrated to ticketing
systems, granular context-linked thresholds, alerting tiered per persona (leadership vs. engineering
see different things)."*

- Our `anomaly` mode is Crawl-level by the Framework's own definition — on-demand, manual,
  single-resource investigation. There's no persistence of a detection baseline across runs, no
  persona-tiered alerting, no ticketing integration.
- **Opportunity**: a `findings/anomalies.json` history that tracks baseline drift run-over-run (we
  already have `compare_runs` in the dashboard — this is the natural next step: don't just diff
  findings, diff the *anomaly baseline itself*).

### B. Reporting & Analytics — the Framework names specific inputs/outputs/KPIs we're missing

Per the Framework: **"Overall Tagging Compliance is greater than 90%"** is a named Measure of
Success — not just "measure coverage," a specific target number. Named outputs include
*"Allocated and unallocated resources coverage reports"* and *"Rate optimization threshold reports
for commitment coverage and vacancy rates."*

- Our `tagging-policy-design` skill measures coverage but has no target threshold baked in (we just
  report the %, we don't flag "below the Framework's own 90% bar").
- We have no "allocated vs unallocated spend" reporting at all — this is a named, expected output
  type we don't produce.
- **Opportunity**: add a 90%-coverage flag to the tagging finding/dashboard, and a new lightweight
  "allocation coverage" panel (% of spend with a complete tag set vs. not) — this is Resource Graph
  - spend data we already pull, just not surfaced as its own metric.

### C. KPIs & Benchmarking — we have zero named KPIs, only ad-hoc numbers

The Framework calls for *"a curated, well-documented set of KPIs... maintained across all FinOps
Scopes... regularly reviewed for relevance."* Right now finops-squad's dashboard shows **raw
totals** (estimated saving, count of findings) but no named, trackable KPI series (e.g. "cost per
environment," "% of spend covered by commitments," "tagging compliance %") that persist and trend
across runs.

- **Opportunity**: a small, named KPI set (3–5 to start, per the Framework's own "start small"
  guidance) tracked in the dashboard's cross-run comparison, not just raw finding counts.

### D. Unit Economics — a capability we don't touch at all

Defined as relating *"cost per transaction / per customer / per workload / per GB stored / per
token"* to business value. This is a meaningful gap for AI-era workloads specifically (the
Framework explicitly calls out "cost per token" as a modern unit).

- We have the raw ingredients (spend by resource group, by service) but never compute a unit
  metric.
- **Opportunity**: this is a bigger lift (needs a volume/usage denominator the squad doesn't
  currently fetch) — reasonable to flag as a **future** capability rather than immediate scope.

### E. Dashboard/UI — direct inspiration from the Microsoft FinOps Toolkit's own Power BI report set

The Toolkit ships 5 named report packs, each with a clear single-sentence purpose:
**Cost summary** (trend + breakdowns), **Rate optimization** (commitment savings + opportunities),
**Invoicing + chargeback** (billed cost vs. invoice reconciliation, chargeback breakdown),
**Policy + governance** (CAF-aligned governance posture metrics), **Workload optimization**
(utilization + efficiency). Our dashboard is currently one flat page mixing all of these together.

- **Opportunity**: restructure `scripts/dashboard.py` into named, Toolkit-style views/tabs (even
  informally, via `st.tabs`) — Cost Summary, Waste & Rightsizing, Governance (tagging/policy),
  rather than one long scroll. This mirrors a proven, user-tested IA rather than inventing our own.
- The Toolkit's **FinOps alerts** tool is literally "scheduled, configurable-schedule scanning for
  idle resources with automated notifications" — exactly our `waste` mode, but *scheduled* rather
  than on-demand. Confirms the iteration-brief/measurement-window work already done is the right
  direction, but a true recurring schedule (e.g. a documented cron/Task Scheduler recipe) is the
  next natural step, not just a manually-triggered "run again."
- The Toolkit's **Azure Optimization Engine** explicitly separates by goal: cost, availability,
  performance, security, operational excellence. Our Analyser modes map well to "cost," but a
  dashboard section explicitly labelled by *which FinOps goal* a finding serves (not just its
  `type`) would mirror this and make the "why does this matter" clearer to a Leadership persona
  specifically.

### F. Personas — the Framework expects persona-differentiated views, we have one dashboard for everyone

*"Alerting and thresholds set differently for different personas... leadership, FinOps team,
engineering, finance may see alerts from anomalous spending differently based on their own
thresholds for action or information."* Right now `scripts/dashboard.py` shows the same view to
everyone.

- **Opportunity**: a persona toggle (Engineering view = findings table + evidence; Leadership view
  = KPI trend + $ totals only) — low effort, reuses data already in the dataframe, just changes
  which panels render.

### G. FinOps Alerts / FinOps hubs — architecture-scale ideas, explicitly out of scope for now

FinOps hubs' architecture (Cost Management export → Data Lake → Data Factory → Fabric/ADX →
Power BI/Copilot agent) is an enterprise-scale platform ($120+/mo). That's a different product tier
than finops-squad's "engineer audits their own subscription" scope (per our own
`copilot-instructions.md` v0.1 decision) — **not** recommending we chase this, just noting it
confirms our architecture choice (lightweight, git-native, IDE-first) is a deliberate, reasonable
alternative point in the market, not an inferior shortcut.

## 3. Summary table

| Idea | Framework/Toolkit source | Effort | Where it'd land |
|---|---|---|---|
| Tagging coverage flagged against the Framework's named 90% bar | Reporting & Analytics capability | Small | `tagging-policy-design` skill + dashboard |
| Allocated vs. unallocated spend panel | Reporting & Analytics named output | Small-Medium | Dashboard + Discovery |
| A named, persisted KPI set (3-5 KPIs) trended across runs | KPIs & Benchmarking capability | Medium | Dashboard cross-run comparison |
| Anomaly baseline persistence (not just per-run detection) | Anomaly Management maturity bar | Medium | `anomaly-explanation` skill + run artifacts |
| Dashboard reorganized into named views (Cost/Waste/Governance) | MS Toolkit Power BI report structure | Small-Medium | `scripts/dashboard.py` |
| Persona-toggle view (Leadership vs. Engineering) | Anomaly Mgmt "persona-tiered alerting" + Personas model | Small | `scripts/dashboard.py` |
| Documented recurring-schedule recipe (not just manual re-run) | FinOps alerts tool | Small (docs only) | `docs/` |
| Unit economics (cost per token/workload) | Unit Economics capability | Large (new data) | Future/deferred |
