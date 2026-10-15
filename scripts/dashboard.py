#!/usr/bin/env python3
"""finops-squad dashboard — interactive visualizer for run artifacts.

Run with:
    streamlit run scripts/dashboard.py

Reads schema-valid artifacts from .finops/runs/<id>/ and renders:
- KPIs (estimated vs realised monthly savings, finding/verified counts)
- Estimated vs Realised savings (never merged — honours the honest-numbers rule)
- Savings by finding type and findings by risk tier
- A sortable findings table with evidence
- Status funnel (proposed -> ... -> verified)
- Spend by service (or a trend, if that shape is present), or an honest "spend data unavailable"
  banner if the run genuinely couldn't retrieve it
- Iteration progress (only if the run captured an optional iteration brief)
- A cross-run comparison (resolved / recurring / new findings vs. another run)

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
    load_findings,
    load_iteration,
    load_json,
    load_verifications,
    list_runs as _list_runs,
)

REPO = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO / ".finops" / "runs"


def list_runs() -> list[Path]:
    return _list_runs(RUNS_DIR)


# ----------------------------------------------------------------------- render
st.set_page_config(page_title="finops-squad dashboard", page_icon="💸", layout="wide")
st.title("💸 finops-squad dashboard")
st.caption("Read-only visualizer for `.finops/runs/<id>/` artifacts. No Azure calls, no mutations.")

runs = list_runs()
if not runs:
    st.warning("No runs found under `.finops/runs/`. Run an audit first.")
    st.stop()

run_name = st.sidebar.selectbox("Run", [p.name for p in runs], index=0)
run = RUNS_DIR / run_name

config = load_json(REPO / ".finops" / "config.json") or {}
spend = load_json(run / "spend.json") or {}
ledger = load_json(run / "reports" / "savings-ledger.json") or {}
findings = load_findings(run)
verifs = load_verifications(run)
df = findings_dataframe(findings, verifs)
iteration = load_iteration(run)

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

# Iteration progress (only if this run captured a brief)
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
        st.dataframe(pd.DataFrame(goal_rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No goals recorded in this iteration brief yet.")

# KPIs
c1, c2, c3, c4 = st.columns(4)
c1.metric("Estimated saving / mo", f"{currency} {est:,.2f}")
c2.metric("Realised saving / mo", f"{currency} {real:,.2f}")
c3.metric("Findings", int(totals.get("findingCount", len(df))))
c4.metric("Verified", int(totals.get("verifiedCount", 0)))

if real == 0 and est > 0:
    st.info(
        f"Realised saving is **{currency} 0.00** — nothing has been remediated and verified yet. "
        "Estimates are never counted as realised."
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
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# Spend panel
st.subheader("Spend")
spend_currency = spend.get("currency", currency)
if spend_currency != currency and str(spend.get("status", "")).lower() == "available":
    st.caption(
        f"Spend is reported in **{spend_currency}** (the subscription's billing currency), which "
        f"may differ from the report default ({currency}). Figures below are shown as returned, "
        "not converted."
    )

if str(spend.get("status", "")).lower() == "unavailable":
    st.warning(
        "**Spend data unavailable** — "
        + spend.get("reason", "cost.query_spend backend not connected.")
    )
elif spend.get("byService"):
    sp = pd.DataFrame(spend["byService"]).sort_values("cost", ascending=False)
    total = spend.get("totalLastMonth", float(sp["cost"].sum()))
    st.metric(f"Total spend ({spend.get('timeframe', 'period')})", f"{spend_currency} {total:,.2f}")
    chart = (
        alt.Chart(sp.head(15))
        .mark_bar()
        .encode(
            x=alt.X("cost:Q", title=f"Cost ({spend_currency})"),
            y=alt.Y("service:N", sort="-x", title=None),
            tooltip=["service", "cost"],
        )
    )
    st.altair_chart(chart, use_container_width=True)
elif spend.get("totalByMonth"):
    sp = pd.DataFrame(
        [{"month": m, "amount": v} for m, v in spend["totalByMonth"].items()]
    ).sort_values("month")
    chart = (
        alt.Chart(sp)
        .mark_line(point=True)
        .encode(x="month:O", y=alt.Y("amount:Q", title=f"Spend ({spend_currency})"), tooltip=["month", "amount"])
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.caption("No spend breakdown available for this run.")

if df.empty:
    st.stop()

# Savings charts
left, right = st.columns(2)

with left:
    st.subheader("Estimated vs Realised")
    comp = pd.DataFrame(
        {"kind": ["Estimated", "Realised"], "amount": [est, real]}
    )
    st.altair_chart(
        alt.Chart(comp).mark_bar().encode(
            x=alt.X("kind:N", title=None),
            y=alt.Y("amount:Q", title=f"{currency}/mo"),
            color=alt.Color("kind:N", scale=alt.Scale(
                domain=["Estimated", "Realised"], range=["#9aa0a6", "#34a853"]), legend=None),
            tooltip=["kind", "amount"],
        ),
        use_container_width=True,
    )

with right:
    st.subheader("Estimated saving by type")
    by_type = (
        df.groupby("type", as_index=False)["estimatedMonthly"].sum().sort_values(
            "estimatedMonthly", ascending=False)
    )
    st.altair_chart(
        alt.Chart(by_type).mark_bar().encode(
            x=alt.X("estimatedMonthly:Q", title=f"{currency}/mo"),
            y=alt.Y("type:N", sort="-x", title=None),
            tooltip=["type", "estimatedMonthly"],
        ),
        use_container_width=True,
    )

# Tier + status
left2, right2 = st.columns(2)

with left2:
    st.subheader("Findings by risk tier")
    by_tier = df.groupby("tier", as_index=False).size().rename(columns={"size": "count"})
    st.altair_chart(
        alt.Chart(by_tier).mark_bar().encode(
            x=alt.X("tier:N", sort=TIER_ORDER, title=None),
            y=alt.Y("count:Q", title="Findings"),
            color=alt.Color("tier:N", scale=alt.Scale(
                domain=list(TIER_COLORS), range=list(TIER_COLORS.values())), legend=None),
            tooltip=["tier", "count"],
        ),
        use_container_width=True,
    )

with right2:
    st.subheader("Status funnel")
    by_status = df.groupby("status", as_index=False).size().rename(columns={"size": "count"})
    st.altair_chart(
        alt.Chart(by_status).mark_bar().encode(
            x=alt.X("status:N", sort=STATUS_ORDER, title=None),
            y=alt.Y("count:Q", title="Findings"),
            tooltip=["status", "count"],
        ),
        use_container_width=True,
    )

# Compare with another run — tells a repeat scan apart from real progress
other_runs = [p.name for p in runs if p.name != run_name]
if other_runs:
    st.subheader("📊 Compare with another run")
    compare_name = st.selectbox(
        "Compare against", other_runs, index=0,
        help="Findings are matched by (type, resourceId), not by id — ids are only stable within a single run.",
    )
    compare_run = RUNS_DIR / compare_name
    compare_findings = load_findings(compare_run)
    # Treat the earlier run (by folder-name sort order, which is the yyyymmdd-hhmm timestamp) as
    # "a" and the later run as "b", regardless of which one is currently selected in the sidebar.
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
                    [{"type": f.get("type"), "resourceId": f.get("resourceId"), "summary": f.get("summary")}
                     for f in diff["resolved"]]
                ),
                use_container_width=True, hide_index=True,
            )
        else:
            st.caption("None — nothing from the earlier run has been resolved.")
    with st.expander("Recurring findings (still open in both runs)"):
        if diff["recurring"]:
            st.dataframe(
                pd.DataFrame(
                    [{"id": f.get("id"), "type": f.get("type"), "tier": f.get("tier"),
                      "resourceId": f.get("resourceId"), "status": f.get("status")}
                     for f in diff["recurring"]]
                ),
                use_container_width=True, hide_index=True,
            )
        else:
            st.caption("None.")

# Findings table
st.subheader("Findings")
tiers = st.multiselect("Filter tier", TIER_ORDER, default=TIER_ORDER)
view = df[df["tier"].isin(tiers)].copy()
view = view.sort_values(["estimatedMonthly"], ascending=False)
st.dataframe(
    view[
        [
            "id", "type", "tier", "estimatedMonthly", "basis", "confidence",
            "effort", "iacMatch", "status", "verifiedResult", "realisedMonthly",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

with st.expander("Finding details & evidence"):
    fid = st.selectbox("Finding", view["id"].tolist())
    detail = next((f for f in findings if f.get("id") == fid), None)
    if detail:
        st.json(detail)
