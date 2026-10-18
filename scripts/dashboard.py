#!/usr/bin/env python3
"""finops-squad dashboard — interactive visualizer for run artifacts.

Run with:
    streamlit run scripts/dashboard.py

Organized into three named views (mirroring the Microsoft FinOps Toolkit's own Power BI report
structure — Cost Summary / Policy & Governance / a KPI-trend view — rather than one long, flat
page):

- 📊 Cost Summary       — headline KPIs, spend by service/trend, estimated vs realised savings.
- 🧹 Waste & Governance — iteration progress, savings by type, risk-tier/status funnels, and the
  full findings table with evidence (Engineering persona only — see the sidebar toggle).
- 📈 KPIs & Trends      — the named FinOps KPI set (tagging compliance, allocation coverage,
  savings opportunity, realised rate, anomaly trend), a run-over-run trend chart, and the
  cross-run comparison (resolved / recurring / new findings).

A sidebar **persona toggle** (Engineering / Leadership) reflects the FinOps Framework's own
guidance that different personas need different levels of detail — Leadership sees KPI cards and
charts; Engineering additionally sees the raw findings table and per-finding evidence.

Everything is read-only. The dashboard never calls Azure and never mutates artifacts.
Pure/IO helpers live in dashboard_helpers.py so they can be unit-tested without a Streamlit
runtime — see tests/test_scripts.py.
"""
from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from dashboard_helpers import (
    STATUS_ORDER,
    TIER_COLORS,
    TIER_ORDER,
    compare_runs,
    findings_dataframe,
    kpi_trend_dataframe,
    load_findings,
    load_iteration,
    load_json,
    load_kpis,
    load_verifications,
    list_runs as _list_runs,
)

REPO = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO / ".finops" / "runs"

KPI_METRIC_LABELS = {
    "estimatedSavingsOpportunity": "Estimated savings opportunity",
    "realisedSavingsRate": "Realised savings rate (%)",
    "taggingCompliance": "Tagging compliance (%)",
    "allocationCoverage": "Allocation coverage (%)",
    "anomalyCount": "Anomaly count",
}


def list_runs() -> list[Path]:
    return _list_runs(RUNS_DIR)


# ----------------------------------------------------------------------- setup
st.set_page_config(page_title="finops-squad dashboard", page_icon="💸", layout="wide")
st.title("💸 finops-squad dashboard")
st.caption("Read-only visualizer for `.finops/runs/<id>/` artifacts. No Azure calls, no mutations.")

runs = list_runs()
if not runs:
    st.warning("No runs found under `.finops/runs/`. Run an audit first.")
    st.stop()

run_name = st.sidebar.selectbox("Run", [p.name for p in runs], index=0)
run = RUNS_DIR / run_name

persona = st.sidebar.radio(
    "View for",
    ["Engineering", "Leadership"],
    index=0,
    help=(
        "The FinOps Framework expects different personas to see different levels of detail. "
        "Leadership sees KPI cards and charts only; Engineering additionally sees the raw "
        "findings table and per-finding evidence."
    ),
)

config = load_json(REPO / ".finops" / "config.json") or {}
spend = load_json(run / "spend.json") or {}
ledger = load_json(run / "reports" / "savings-ledger.json") or {}
findings = load_findings(run)
verifs = load_verifications(run)
df = findings_dataframe(findings, verifs)
iteration = load_iteration(run)
kpis = load_kpis(run)

currency = ledger.get("currency") or config.get("currency") or "AUD"
sub = spend.get("subscriptionId") or (config.get("subscriptions") or ["—"])[0]
st.sidebar.markdown(f"**Subscription**\n\n`{sub}`")
st.sidebar.markdown(f"**Currency**: {currency}")
st.sidebar.markdown(f"**Price basis**: {config.get('priceBasis', '—')}")
if iteration:
    st.sidebar.markdown(f"**Iteration**: {iteration.get('iterationId', '—')}")

mixed_currencies = bool(ledger.get("mixedCurrencies"))
if mixed_currencies:
    st.warning(
        "⚠️ **This run mixes currencies across findings.** The KPIs and charts below reflect only "
        f"the primary currency (**{currency}**, the one with the most findings) — see the "
        "'Savings by currency' breakdown further down for the rest. Totals are never summed "
        "across currencies."
    )

totals = ledger.get("totals", {})
est = totals.get("estimatedMonthly", float(df["estimatedMonthly"].sum()) if not df.empty else 0.0)
real = totals.get("realisedMonthly", float(df["realisedMonthly"].sum()) if not df.empty else 0.0)

tab_cost, tab_waste, tab_kpis = st.tabs(
    ["📊 Cost Summary", "🧹 Waste & Governance", "📈 KPIs & Trends"]
)

# --------------------------------------------------------------------- Cost Summary tab
with tab_cost:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Estimated saving / mo", f"{currency} {est:,.2f}")
    c2.metric("Realised saving / mo", f"{currency} {real:,.2f}")
    c3.metric("Findings", int(totals.get("findingCount", len(df))))
    c4.metric("Verified", int(totals.get("verifiedCount", 0)))

    if real == 0 and est > 0:
        st.info(
            f"Realised saving is **{currency} 0.00** — nothing has been remediated and verified "
            "yet. Estimates are never counted as realised."
        )

    if mixed_currencies:
        st.subheader("Savings by currency")
        by_currency = ledger.get("byCurrency", {})
        rows = [
            {
                "currency": c,
                "estimatedMonthly": v["totals"]["estimatedMonthly"],
                "realisedMonthly": v["totals"]["realisedMonthly"],
                "findingCount": v["totals"]["findingCount"],
            }
            for c, v in sorted(by_currency.items())
        ]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.subheader("Spend")
    spend_currency = spend.get("currency", currency)
    if spend_currency != currency and str(spend.get("status", "")).lower() == "available":
        st.caption(
            f"Spend is reported in **{spend_currency}** (the subscription's billing currency), "
            f"which may differ from the report default ({currency}). Figures below are shown as "
            "returned, not converted."
        )

    if str(spend.get("status", "")).lower() == "unavailable":
        st.warning(
            "**Spend data unavailable** — "
            + spend.get("reason", "cost.query_spend backend not connected.")
        )
    elif spend.get("byService"):
        sp = pd.DataFrame(spend["byService"]).sort_values("cost", ascending=False)
        total = spend.get("totalLastMonth", float(sp["cost"].sum()))
        st.metric(
            f"Total spend ({spend.get('timeframe', 'period')})", f"{spend_currency} {total:,.2f}"
        )
        chart = (
            alt.Chart(sp.head(15))
            .mark_bar()
            .encode(
                x=alt.X("cost:Q", title=f"Cost ({spend_currency})"),
                y=alt.Y("service:N", sort="-x", title=None),
                tooltip=["service", "cost"],
            )
        )
        st.altair_chart(chart, width="stretch")
    elif spend.get("totalByMonth"):
        sp = pd.DataFrame(
            [{"month": m, "amount": v} for m, v in spend["totalByMonth"].items()]
        ).sort_values("month")
        chart = (
            alt.Chart(sp)
            .mark_line(point=True)
            .encode(
                x="month:O",
                y=alt.Y("amount:Q", title=f"Spend ({spend_currency})"),
                tooltip=["month", "amount"],
            )
        )
        st.altair_chart(chart, width="stretch")
    else:
        st.caption("No spend breakdown available for this run.")

    if not df.empty:
        st.subheader("Estimated vs Realised")
        comp = pd.DataFrame({"kind": ["Estimated", "Realised"], "amount": [est, real]})
        st.altair_chart(
            alt.Chart(comp)
            .mark_bar()
            .encode(
                x=alt.X("kind:N", title=None),
                y=alt.Y("amount:Q", title=f"{currency}/mo"),
                color=alt.Color(
                    "kind:N",
                    scale=alt.Scale(domain=["Estimated", "Realised"], range=["#9aa0a6", "#34a853"]),
                    legend=None,
                ),
                tooltip=["kind", "amount"],
            ),
            width="stretch",
        )

if df.empty:
    with tab_waste:
        st.caption("No findings in this run yet.")
    with tab_kpis:
        st.caption("No findings in this run yet.")
    st.stop()

# --------------------------------------------------------------------- Waste & Governance tab
with tab_waste:
    if iteration:
        st.subheader("🎯 Iteration progress")
        goals = iteration.get("goals", [])
        window = iteration.get("measurementWindow", {})
        st.caption(
            f"**{iteration.get('iterationId', 'unnamed iteration')}** · "
            f"window {window.get('from', '?')} → {window.get('to', '?')} · "
            f"status: {iteration.get('status', 'in-progress')}"
        )
        if iteration.get("constraints"):
            st.caption("Guardrails: " + "; ".join(iteration["constraints"]))
        if goals:
            goal_rows = []
            for g in goals:
                baseline = g.get("baseline", {})
                target = g.get("target", {})
                current = g.get("current", baseline)
                goal_rows.append(
                    {
                        "goal": g.get("description", "—"),
                        "metric": g.get("metric", "—"),
                        "baseline": baseline.get("value"),
                        "current": current.get("value"),
                        "target": target.get("value"),
                    }
                )
            st.dataframe(pd.DataFrame(goal_rows), width="stretch", hide_index=True)
        else:
            st.caption("No goals recorded in this iteration brief yet.")

    left, right = st.columns(2)
    with left:
        st.subheader("Estimated saving by type")
        by_type = (
            df.groupby("type", as_index=False)["estimatedMonthly"]
            .sum()
            .sort_values("estimatedMonthly", ascending=False)
        )
        st.altair_chart(
            alt.Chart(by_type)
            .mark_bar()
            .encode(
                x=alt.X("estimatedMonthly:Q", title=f"{currency}/mo"),
                y=alt.Y("type:N", sort="-x", title=None),
                tooltip=["type", "estimatedMonthly"],
            ),
            width="stretch",
        )

    with right:
        st.subheader("Findings by risk tier")
        by_tier = df.groupby("tier", as_index=False).size().rename(columns={"size": "count"})
        st.altair_chart(
            alt.Chart(by_tier)
            .mark_bar()
            .encode(
                x=alt.X("tier:N", sort=TIER_ORDER, title=None),
                y=alt.Y("count:Q", title="Findings"),
                color=alt.Color(
                    "tier:N",
                    scale=alt.Scale(domain=list(TIER_COLORS), range=list(TIER_COLORS.values())),
                    legend=None,
                ),
                tooltip=["tier", "count"],
            ),
            width="stretch",
        )

    st.subheader("Status funnel")
    by_status = df.groupby("status", as_index=False).size().rename(columns={"size": "count"})
    st.altair_chart(
        alt.Chart(by_status)
        .mark_bar()
        .encode(
            x=alt.X("status:N", sort=STATUS_ORDER, title=None),
            y=alt.Y("count:Q", title="Findings"),
            tooltip=["status", "count"],
        ),
        width="stretch",
    )

    if persona == "Engineering":
        st.subheader("Findings")
        tiers = st.multiselect("Filter tier", TIER_ORDER, default=TIER_ORDER, key="tier_filter")
        view = df[df["tier"].isin(tiers)].copy()
        view = view.sort_values(["estimatedMonthly"], ascending=False)
        st.dataframe(
            view[
                [
                    "id", "type", "tier", "estimatedMonthly", "basis", "confidence",
                    "effort", "iacMatch", "status", "verifiedResult", "realisedMonthly",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

        with st.expander("Finding details & evidence"):
            fid = st.selectbox("Finding", view["id"].tolist())
            detail = next((f for f in findings if f.get("id") == fid), None)
            if detail:
                st.json(detail)
    else:
        st.caption(
            "Switch to the Engineering view (sidebar) for the full finding-level table and "
            "per-finding evidence."
        )

# --------------------------------------------------------------------- KPIs & Trends tab
with tab_kpis:
    if kpis is None:
        st.caption(
            "No KPI set generated for this run yet. Run "
            "`python scripts/kpis.py .finops/runs/<id>/ --runs-dir .finops/runs`."
        )
    else:
        kc1, kc2, kc3, kc4, kc5 = st.columns(5)

        tc = kpis["kpis"]["taggingCompliance"]
        tc_val = f"{tc['value']:.1f}%" if tc["value"] is not None else "—"
        tc_delta = (
            "✅ meets 90% target"
            if tc.get("meetsTarget")
            else ("below 90% target" if tc["value"] is not None else None)
        )
        kc1.metric("Tagging compliance", tc_val, tc_delta)

        ac = kpis["kpis"]["allocationCoverage"]
        kc2.metric(
            "Allocation coverage", f"{ac['value']:.1f}%" if ac["value"] is not None else "—"
        )

        es = kpis["kpis"]["estimatedSavingsOpportunity"]
        kc3.metric("Est. savings opportunity", f"{es['currency']} {es['value']:,.2f}")

        rr = kpis["kpis"]["realisedSavingsRate"]
        kc4.metric("Realised savings rate", f"{rr['value']:.1f}%")

        an = kpis["kpis"]["anomalyCount"]
        trend_arrow = {"up": "📈", "down": "📉", "flat": "➡️", "unavailable": ""}.get(
            an["trend"], ""
        )
        kc5.metric(
            "Anomaly count",
            an["value"],
            f"{trend_arrow} {an['trend']}" if an["trend"] != "unavailable" else None,
        )

        with st.expander("What do these mean / why unavailable?"):
            for name, kpi in kpis["kpis"].items():
                note = kpi.get("note", "")
                st.markdown(f"**{KPI_METRIC_LABELS.get(name, name)}** — {note}")

    st.subheader("Trend across runs")
    metric_key = st.selectbox(
        "Metric", list(KPI_METRIC_LABELS), format_func=lambda k: KPI_METRIC_LABELS[k]
    )
    oldest_first = sorted(runs, key=lambda p: p.name)
    trend_df = kpi_trend_dataframe(oldest_first, metric_key)
    available_df = trend_df[trend_df["available"]]
    if available_df.empty:
        st.caption("No runs with this KPI computed yet.")
    else:
        st.altair_chart(
            alt.Chart(available_df)
            .mark_line(point=True)
            .encode(
                x=alt.X("runId:N", sort=list(trend_df["runId"]), title="Run"),
                y=alt.Y("value:Q", title=KPI_METRIC_LABELS[metric_key]),
                tooltip=["runId", "value"],
            ),
            width="stretch",
        )
        missing = len(trend_df) - len(available_df)
        if missing:
            st.caption(f"{missing} run(s) omitted — this KPI wasn't computed for them.")

    # Compare with another run — tells a repeat scan apart from real progress
    other_runs = [p.name for p in runs if p.name != run_name]
    if other_runs:
        st.subheader("📊 Compare with another run")
        compare_name = st.selectbox(
            "Compare against",
            other_runs,
            index=0,
            help=(
                "Findings are matched by (type, resourceId), not by id — ids are only stable "
                "within a single run."
            ),
        )
        compare_run = RUNS_DIR / compare_name
        compare_findings = load_findings(compare_run)
        # Treat the earlier run (by folder-name sort order, the yyyymmdd-hhmm timestamp) as "a"
        # and the later run as "b", regardless of which one is currently selected in the sidebar.
        earlier, later = sorted([(compare_name, compare_findings), (run_name, findings)])
        diff = compare_runs(earlier[1], later[1])
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Resolved since earlier run", len(diff["resolved"]))
        cc2.metric("Still recurring", len(diff["recurring"]))
        cc3.metric("New this run", len(diff["new"]))
        st.caption(f"Earlier run: `{earlier[0]}` · Later run: `{later[0]}`")
        with st.expander("Resolved findings (no longer present)"):
            if diff["resolved"]:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "type": f.get("type"),
                                "resourceId": f.get("resourceId"),
                                "summary": f.get("summary"),
                            }
                            for f in diff["resolved"]
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.caption("None — nothing from the earlier run has been resolved.")
        with st.expander("Recurring findings (still open in both runs)"):
            if diff["recurring"]:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "id": f.get("id"),
                                "type": f.get("type"),
                                "tier": f.get("tier"),
                                "resourceId": f.get("resourceId"),
                                "status": f.get("status"),
                            }
                            for f in diff["recurring"]
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.caption("None.")
