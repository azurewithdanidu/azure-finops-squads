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

Everything is read-only. The dashboard never calls Azure and never mutates artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

REPO = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO / ".finops" / "runs"

TIER_ORDER = ["T0", "T1", "T2", "T3"]
TIER_COLORS = {"T0": "#34a853", "T1": "#4285f4", "T2": "#f9ab00", "T3": "#ea4335"}
STATUS_ORDER = ["proposed", "approved", "pr-open", "merged", "verified", "rejected"]


# --------------------------------------------------------------------------- IO
def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_runs() -> list[Path]:
    if not RUNS_DIR.is_dir():
        return []
    return sorted((p for p in RUNS_DIR.iterdir() if p.is_dir()), reverse=True)


def load_findings(run: Path) -> list[dict]:
    findings: list[dict] = []
    fdir = run / "findings"
    if not fdir.is_dir():
        return findings
    for path in sorted(fdir.glob("*.json")):
        doc = load_json(path)
        if doc is None:
            continue
        items = doc if isinstance(doc, list) else doc.get("findings", [doc])
        for item in items:
            if isinstance(item, dict) and "id" in item:
                findings.append(item)
    return findings


def load_verifications(run: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    vdir = run / "verification"
    if not vdir.is_dir():
        return out
    for path in sorted(vdir.glob("*.json")):
        doc = load_json(path)
        if isinstance(doc, dict) and "findingId" in doc:
            out[doc["findingId"]] = doc
    return out


def findings_dataframe(findings: list[dict], verifs: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for f in findings:
        saving = f.get("estimatedMonthlySaving", {}) or {}
        iac = f.get("iacMatch", {}) or {}
        ver = verifs.get(f.get("id"))
        rows.append(
            {
                "id": f.get("id"),
                "type": f.get("type"),
                "tier": f.get("tier"),
                "estimatedMonthly": float(saving.get("amount", 0) or 0),
                "currency": saving.get("currency", "AUD"),
                "basis": saving.get("basis"),
                "confidence": f.get("confidence"),
                "effort": f.get("effort"),
                "iacMatch": iac.get("status"),
                "status": f.get("status"),
                "verifiedResult": (ver or {}).get("result"),
                "realisedMonthly": float((ver or {}).get("realisedSaving", 0) or 0)
                if ver and ver.get("result") in {"confirmed", "partial"}
                else 0.0,
                "resourceId": f.get("resourceId"),
                "summary": f.get("summary"),
            }
        )
    return pd.DataFrame(rows)


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

currency = ledger.get("currency") or config.get("currency") or "AUD"
sub = spend.get("subscriptionId") or (config.get("subscriptions") or ["—"])[0]
st.sidebar.markdown(f"**Subscription**\n\n`{sub}`")
st.sidebar.markdown(f"**Currency**: {currency}")
st.sidebar.markdown(f"**Price basis**: {config.get('priceBasis', '—')}")

totals = ledger.get("totals", {})
est = totals.get("estimatedMonthly", float(df["estimatedMonthly"].sum()) if not df.empty else 0.0)
real = totals.get("realisedMonthly", float(df["realisedMonthly"].sum()) if not df.empty else 0.0)

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
