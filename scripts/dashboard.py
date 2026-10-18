#!/usr/bin/env python3
"""finops-squad dashboard — interactive visualizer for run artifacts.

Run with:
    streamlit run scripts/dashboard.py

Organized into three named views (mirroring the Microsoft FinOps Toolkit's own Power BI report
structure — Cost Summary / Policy & Governance / a KPI-trend view — rather than one long, flat
page):

- Cost Summary       — headline KPIs, spend by service/trend, estimated vs realised savings.
- Waste & Governance — iteration progress, savings by type, risk-tier/status funnels, and the
  full findings table with a per-finding detail view (Engineering persona only).
- KPIs & Trends      — the named FinOps KPI set (tagging compliance, allocation coverage,
  savings opportunity, realised rate, anomaly trend, unit economics), a run-over-run trend chart,
  and the cross-run comparison (resolved / recurring / new findings).

The run selector and a **persona switch** (Engineering / Leadership) sit in a top control row, so
the page works with the sidebar collapsed. The switch reflects the FinOps Framework's guidance that
different personas need different levels of detail — Leadership sees KPI cards and charts;
Engineering additionally sees the findings table and per-finding evidence.

Everything is read-only. The dashboard never calls Azure and never mutates artifacts.
Pure/IO helpers live in dashboard_helpers.py, design tokens in dashboard_theme.py and chart
builders in dashboard_charts.py so they can be unit-tested without a Streamlit runtime — see
tests/test_scripts.py. Artifact text is untrusted: it is rendered through native components only
(no raw HTML) and Markdown-escaped via dashboard_helpers.md_escape.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

import dashboard_theme as T
from dashboard_charts import hbar_chart, month_line_chart, trend_chart, vbar_chart
from dashboard_helpers import (
    STATUS_ORDER,
    TIER_ORDER,
    compare_runs,
    confidence_label,
    findings_dataframe,
    is_approximate,
    kpi_trend_dataframe,
    load_findings,
    load_iteration,
    load_json,
    load_kpis,
    load_verifications,
    md_escape,
    money_format,
    run_fingerprint,
    safe_url,
    short_id,
    list_runs as _list_runs,
)

REPO = Path(__file__).resolve().parent.parent
# FINOPS_RUNS_DIR lets tests (and unusual layouts) point the dashboard at another runs folder.
RUNS_DIR = Path(os.environ.get("FINOPS_RUNS_DIR") or REPO / ".finops" / "runs")
CONFIG_PATH = RUNS_DIR.parent / "config.json"

# unitEconomics is intentionally excluded here: its unit/method can differ run-to-run
# (azure-openai-tokens vs manual-denominator vs unavailable), so a single trend line would compare
# incompatible numbers. It's still shown as a headline card below, just not trended -- see
# KPI_NOTE_LABELS for its display label in the explainer expander.
KPI_METRIC_LABELS = {
    "estimatedSavingsOpportunity": "Estimated savings opportunity",
    "realisedSavingsRate": "Realised savings rate (%)",
    "taggingCompliance": "Tagging compliance (%)",
    "allocationCoverage": "Allocation coverage (%)",
    "anomalyCount": "Anomaly count",
}

# Display labels for every KPI's note in the "What do these mean?" expander -- a superset of
# KPI_METRIC_LABELS that also covers unitEconomics, which isn't trendable (see above) but still
# needs a friendly label instead of its raw JSON key.
KPI_NOTE_LABELS = {**KPI_METRIC_LABELS, "unitEconomics": "Unit economics"}

PERSONAS = ["Engineering", "Leadership"]
PERSONA_HELP = (
    "The FinOps Framework expects different personas to see different levels of detail. "
    "Leadership sees KPI cards and charts only; Engineering additionally sees the raw "
    "findings table and per-finding evidence."
)


def list_runs() -> list[Path]:
    return _list_runs(RUNS_DIR)


# -------------------------------------------------------------------- cached file loading
# Keyed on each file's mtime/size (run_fingerprint) so reruns triggered by widgets don't re-read
# and re-parse every artifact; an artifact changing on disk invalidates the entry.
@st.cache_data(show_spinner=False)
def _load_run(run_dir: str, fingerprint: tuple) -> dict:
    run = Path(run_dir)
    return {
        "spend": load_json(run / "spend.json") or {},
        "ledger": load_json(run / "reports" / "savings-ledger.json") or {},
        "findings": load_findings(run),
        "verifs": load_verifications(run),
        "iteration": load_iteration(run),
        "kpis": load_kpis(run),
    }


@st.cache_data(show_spinner=False)
def _load_config(path: str, mtime_ns: int) -> dict:
    return load_json(Path(path)) or {}


@st.cache_data(show_spinner=False)
def _kpi_history(run_dirs: tuple, fingerprint: tuple) -> dict:
    runs_oldest_first = [Path(p) for p in run_dirs]
    return {key: kpi_trend_dataframe(runs_oldest_first, key) for key in KPI_METRIC_LABELS}


def _kpis_fingerprint(runs: list[Path]) -> tuple:
    out = []
    for r in runs:
        try:
            s = (r / "reports" / "kpis.json").stat()
            out.append((r.name, s.st_mtime_ns, s.st_size))
        except OSError:
            out.append((r.name, 0, 0))
    return tuple(out)


def load_run(run: Path) -> dict:
    return _load_run(str(run), run_fingerprint(run))


# -------------------------------------------------------------------------- small UI helpers
def empty_state(title: str, hint: str, icon: str = ":material/inbox:") -> None:
    """A friendly empty state: what is missing and the next step."""
    with st.container(border=True):
        st.markdown(f"{icon} **{title}**")
        st.caption(hint)


def kpi_card(
    container,
    label: str,
    value,
    *,
    delta: str | None = None,
    help: str | None = None,
    history: list[float] | None = None,
    note: str | None = None,
) -> None:
    """A bordered KPI card; sparkline from run history when there are at least two points."""
    with container.container(border=True):
        spark = history if history and len(history) >= 2 else None
        st.metric(
            label,
            value,
            delta,
            delta_color="off",
            delta_arrow="off",
            help=help,
            chart_data=spark,
            chart_type="line",
        )
        if note:
            st.caption(note)


def card_grid(cards: list[dict], per_row: int) -> None:
    for start in range(0, len(cards), per_row):
        cols = st.columns(per_row)
        for col, card in zip(cols, cards[start : start + per_row]):
            kpi_card(col, **card)


def theme_mode() -> str:
    try:
        return "dark" if st.context.theme.type == "dark" else "light"
    except Exception:  # theme info is unavailable in some runtimes (e.g. AppTest)
        return "light"


def chart(c) -> None:
    st.altair_chart(c, width="stretch")


# ----------------------------------------------------------------------- setup
st.set_page_config(
    page_title="finops-squad",
    page_icon=":material/savings:",
    layout="wide",
    initial_sidebar_state="collapsed",
)
try:
    T.register_altair_theme()
except Exception:  # a theme problem must never take the dashboard down
    pass
mode = theme_mode()

runs = list_runs()

# Header row first (before any file is read) so the page has structure immediately on first load.
head_name, head_run, head_persona = st.columns([2, 3, 3], vertical_alignment="center")
head_name.subheader("finops-squad")
meta = st.container()  # filled once the selected run has loaded

if not runs:
    empty_state(
        "No runs found yet",
        "Ask the Orchestrator agent to run an audit — it writes artifacts to "
        "`.finops/runs/<id>/`. Then reload this page.",
        ":material/folder_off:",
    )
    st.stop()

run_name = head_run.selectbox("Run", [p.name for p in runs], index=0, key="run_name")
run = RUNS_DIR / run_name
persona = (
    head_persona.segmented_control(
        "View for", PERSONAS, default=PERSONAS[0], key="persona", help=PERSONA_HELP
    )
    or PERSONAS[0]  # deselecting the control falls back to the default view
)

try:
    config_mtime = CONFIG_PATH.stat().st_mtime_ns
except OSError:
    config_mtime = 0
config = _load_config(str(CONFIG_PATH), config_mtime)
data = load_run(run)
spend, ledger, findings, verifs = data["spend"], data["ledger"], data["findings"], data["verifs"]
iteration, kpis = data["iteration"], data["kpis"]
df = findings_dataframe(findings, verifs)

currency = ledger.get("currency") or config.get("currency") or "AUD"
sub = spend.get("subscriptionId") or (config.get("subscriptions") or ["—"])[0]
price_basis = config.get("priceBasis", "—")
window = (iteration or {}).get("measurementWindow") or {}
if window.get("from") or window.get("to"):
    window_text = f"{window.get('from', '?')} → {window.get('to', '?')}"
else:
    window_text = spend.get("timeframe") or "—"

with meta:
    st.markdown(
        f"Subscription **{md_escape(short_id(sub))}** · Run **{md_escape(run_name)}** · "
        f"Window **{md_escape(window_text)}** &nbsp; "
        f":gray-badge[:material/payments: {md_escape(currency)}] "
        f":gray-badge[:material/sell: Price basis: {md_escape(price_basis)}]"
        + (
            f" :gray-badge[:material/flag: Iteration {md_escape(iteration.get('iterationId', '—'))}]"
            if iteration
            else ""
        )
    )

mixed_currencies = bool(ledger.get("mixedCurrencies"))
if mixed_currencies:
    st.warning(
        "**This run mixes currencies across findings.** The KPIs and charts below reflect only "
        f"the primary currency (**{md_escape(currency)}**, the one with the most findings) — see "
        "the 'Savings by currency' breakdown further down for the rest. Totals are never summed "
        "across currencies.",
        icon=":material/warning:",
    )

totals = ledger.get("totals", {})
est = totals.get("estimatedMonthly", float(df["estimatedMonthly"].sum()) if not df.empty else 0.0)
real = totals.get("realisedMonthly", float(df["realisedMonthly"].sum()) if not df.empty else 0.0)

# Sparkline history: every run up to (and including) the selected one, oldest first.
oldest_first = sorted(runs, key=lambda p: p.name)
history_all = _kpi_history(tuple(str(p) for p in oldest_first), _kpis_fingerprint(oldest_first))


def spark(metric_key: str) -> list[float]:
    h = history_all[metric_key]
    h = h[(h["runId"] <= run_name) & h["available"]]
    return [float(v) for v in h["value"]]


tab_cost, tab_waste, tab_kpis = st.tabs(
    [
        ":material/payments: Cost Summary",
        ":material/cleaning_services: Waste & Governance",
        ":material/trending_up: KPIs & Trends",
    ]
)

# --------------------------------------------------------------------- Cost Summary tab
with tab_cost:
    card_grid(
        [
            {"label": "Estimated saving / mo", "value": f"{currency} {est:,.2f}"},
            {"label": "Realised saving / mo", "value": f"{currency} {real:,.2f}"},
            {"label": "Findings", "value": int(totals.get("findingCount", len(df)))},
            {"label": "Verified", "value": int(totals.get("verifiedCount", 0))},
        ],
        per_row=4,
    )

    if real == 0 and est > 0:
        st.info(
            f"Realised saving is **{md_escape(currency)} 0.00** — nothing has been remediated and "
            "verified yet. Estimates are never counted as realised.",
            icon=":material/info:",
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
        st.dataframe(
            pd.DataFrame(rows),
            width="stretch",
            hide_index=True,
            column_config={
                "currency": st.column_config.TextColumn("Currency"),
                "estimatedMonthly": st.column_config.NumberColumn("Estimated / mo", format="%.2f"),
                "realisedMonthly": st.column_config.NumberColumn("Realised / mo", format="%.2f"),
                "findingCount": st.column_config.NumberColumn("Findings", format="%d"),
            },
        )

    spend_col, ver_col = st.columns([3, 2])
    with spend_col:
        with st.container(border=True):
            st.subheader("Spend")
            spend_currency = spend.get("currency", currency)
            if spend_currency != currency and str(spend.get("status", "")).lower() == "available":
                st.caption(
                    f"Spend is reported in **{md_escape(spend_currency)}** (the subscription's "
                    f"billing currency), which may differ from the report default "
                    f"({md_escape(currency)}). Figures below are shown as returned, not converted."
                )

            if str(spend.get("status", "")).lower() == "unavailable":
                st.warning(
                    "**Spend data unavailable** — "
                    + md_escape(spend.get("reason", "cost.query_spend backend not connected.")),
                    icon=":material/cloud_off:",
                )
            elif spend.get("byService") and all(
                isinstance(r, dict) and "cost" in r for r in spend["byService"]
            ):  # other shapes (e.g. per-month rows) fall through to the empty state
                sp = pd.DataFrame(spend["byService"]).sort_values("cost", ascending=False)
                total = spend.get("totalLastMonth", float(sp["cost"].sum()))
                st.metric(
                    f"Total spend ({spend.get('timeframe', 'period')})",
                    f"{spend_currency} {total:,.2f}",
                )
                st.caption(f"Top 15 services by cost ({spend_currency})")
                chart(hbar_chart(sp.head(15), "service", "cost", ["service", "cost"], mode))
            elif spend.get("totalByMonth"):
                sp = pd.DataFrame(
                    [{"month": m, "amount": v} for m, v in spend["totalByMonth"].items()]
                ).sort_values("month")
                chart(month_line_chart(sp, f"Spend ({spend_currency})", mode))
            else:
                empty_state(
                    "No spend breakdown for this run",
                    "Run Discovery with a connected cost backend to capture spend by service.",
                    ":material/query_stats:",
                )

    with ver_col:
        with st.container(border=True):
            st.subheader("Estimated vs realised")
            if df.empty:
                empty_state(
                    "No findings yet",
                    "Savings appear here once the Analyser has produced findings for this run.",
                )
            else:
                st.caption(f"{currency} per month — estimates are never counted as realised")
                comp = pd.DataFrame({"kind": ["Estimated", "Realised"], "amount": [est, real]})
                chart(
                    vbar_chart(
                        comp,
                        "kind",
                        "amount",
                        ["Estimated", "Realised"],
                        {"Estimated": T.ESTIMATED, "Realised": T.REALISED},
                        mode=mode,
                    )
                )

if df.empty:
    with tab_waste:
        empty_state(
            "No findings in this run yet",
            "Ask the Analyser to run a mode (waste, rightsizing, tagging, …) and reload.",
        )
    with tab_kpis:
        empty_state(
            "No findings in this run yet",
            "KPIs are computed from findings — run an Analyser mode first, then "
            "`python scripts/kpis.py .finops/runs/<id>/ --runs-dir .finops/runs`.",
        )
    st.stop()


# --------------------------------------------------------------------- finding detail view
def render_finding(fid: str) -> None:
    """Structured detail for one finding: summary, key facts, evidence cards, raw JSON."""
    f = next((x for x in findings if x.get("id") == fid), None)
    rows = df[df["id"] == fid]
    if f is None or rows.empty:
        empty_state("Finding not found", "Select another row in the findings table.")
        return
    row = rows.iloc[0]
    tier = f.get("tier")
    st.markdown(f"#### {md_escape(f.get('type', 'finding'))} · {md_escape(fid)}")
    st.markdown(md_escape(f.get("summary")) or "_No summary recorded._")

    cur = md_escape(row["currency"])
    facts = [
        ("Risk tier", T.TIER_LABELS.get(tier, tier or "—")),
        ("Est. saving / mo", f"{cur} {row['estimatedMonthly']:,.2f}"),
        ("Price basis", row["basis"] or "—"),
        ("Confidence", confidence_label(row["confidence"])),
        ("Effort", row["effort"] or "—"),
        ("IaC match", row["iacMatch"] or "—"),
        ("Status", row["status"] or "—"),
        ("Verified result", row["verifiedResult"] or "not verified"),
        ("Realised / mo", f"{cur} {row['realisedMonthly']:,.2f}"),
    ]
    st.markdown("##### Key facts")
    for start in range(0, len(facts), 3):
        for col, (label, value) in zip(st.columns(3), facts[start : start + 3]):
            with col.container(border=True):
                st.caption(label)
                st.markdown(f"**{md_escape(value)}**")

    st.caption("Resource")
    st.code(str(f.get("resourceId") or "—"), language=None, wrap_lines=True)
    pr = safe_url(f.get("prUrl"))
    if pr:
        st.link_button("Open pull request", pr, icon=":material/open_in_new:")

    st.markdown("##### Evidence")
    evidence = [e for e in (f.get("evidence") or []) if isinstance(e, dict)]
    if not evidence:
        empty_state("No evidence recorded", "Every finding should cite evidence — re-run the Analyser.")
    for ev in evidence:
        with st.container(border=True):
            st.markdown(f"**{md_escape(ev.get('capability', 'evidence'))}**")
            st.caption(
                f"{md_escape(ev.get('tool', '—'))} · window: {md_escape(ev.get('timeWindow', '—'))}"
            )
            st.markdown(md_escape(ev.get("observation")))
            if ev.get("query"):
                st.code(str(ev["query"]), language=None, wrap_lines=True)

    with st.expander("Raw JSON (Engineering)"):
        st.json(f)


if hasattr(st, "dialog"):

    @st.dialog("Finding details", width="large")
    def finding_dialog(fid: str) -> None:
        render_finding(fid)

else:
    finding_dialog = None


# --------------------------------------------------------------------- Waste & Governance tab
with tab_waste:
    if iteration:
        st.subheader("Iteration progress")
        goals = iteration.get("goals", [])
        st.caption(
            f"**{md_escape(iteration.get('iterationId', 'unnamed iteration'))}** · "
            f"window {md_escape(window.get('from', '?'))} → {md_escape(window.get('to', '?'))} · "
            f"status: {md_escape(iteration.get('status', 'in-progress'))}"
        )
        if iteration.get("constraints"):
            st.caption("Guardrails: " + md_escape("; ".join(iteration["constraints"])))
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
            empty_state(
                "No goals recorded yet",
                "Add goals to this run's iteration brief (iteration.json) to track progress here.",
                ":material/flag:",
            )

    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("Estimated saving by type")
            # Never blend currencies: in a mixed-currency run chart only the primary currency.
            by_type_src = df[df["currency"] == currency] if mixed_currencies else df
            st.caption(
                f"{currency}/mo" + (" — primary currency only" if mixed_currencies else "")
            )
            by_type = (
                by_type_src.groupby("type", as_index=False)["estimatedMonthly"]
                .sum()
                .sort_values("estimatedMonthly", ascending=False)
            )
            chart(hbar_chart(by_type, "type", "estimatedMonthly", ["type", "estimatedMonthly"], mode))

    with right:
        with st.container(border=True):
            st.subheader("Findings by risk tier")
            st.caption("Number of findings; tier shown as text and colour")
            by_tier = df.groupby("tier", as_index=False).size().rename(columns={"size": "count"})
            by_tier["tierLabel"] = by_tier["tier"].map(T.TIER_LABELS).fillna(by_tier["tier"])
            chart(
                vbar_chart(
                    by_tier,
                    "tierLabel",
                    "count",
                    [T.TIER_LABELS[t] for t in TIER_ORDER],
                    {T.TIER_LABELS[t]: c for t, c in T.TIER_COLORS.items()},
                    tooltip=["tierLabel", "count"],
                    mode=mode,
                    decimals=0,
                )
            )

    with st.container(border=True):
        st.subheader("Status funnel")
        by_status = df.groupby("status", as_index=False).size().rename(columns={"size": "count"})
        chart(vbar_chart(by_status, "status", "count", STATUS_ORDER, tooltip=["status", "count"], mode=mode, decimals=0))

    if persona == "Engineering":
        st.subheader("Findings")
        tiers = st.multiselect(
            "Filter tier",
            TIER_ORDER,
            default=TIER_ORDER,
            key="tier_filter",
            format_func=lambda t: T.TIER_LABELS.get(t, t),
        )
        view = df[df["tier"].isin(tiers)].copy()
        view = view.sort_values(["estimatedMonthly"], ascending=False)
        view["tierLabel"] = view["tier"].map(T.TIER_LABELS).fillna(view["tier"])
        view["confidenceLabel"] = view["confidence"].map(confidence_label)
        row_mixed = mixed_currencies or df["currency"].nunique() > 1
        money = money_format(currency, row_mixed)

        if view.empty:
            empty_state(
                "No findings match this filter",
                "Add a risk tier back in the filter above to see findings again.",
                ":material/filter_alt_off:",
            )
        else:
            columns = ["id", "type", "tierLabel", "estimatedMonthly"]
            if row_mixed:
                columns.append("currency")
            columns += [
                "basis", "confidenceLabel", "effort", "iacMatch", "status", "verifiedResult",
                "realisedMonthly",
            ]
            column_config = {
                "id": st.column_config.TextColumn("ID", width="small"),
                "type": st.column_config.TextColumn("Type"),
                "tierLabel": st.column_config.TextColumn("Risk tier"),
                "estimatedMonthly": st.column_config.NumberColumn("Est. saving / mo", format=money),
                "currency": st.column_config.TextColumn("Currency", width="small"),
                "basis": st.column_config.TextColumn("Price basis"),
                "confidenceLabel": st.column_config.TextColumn("Confidence"),
                "effort": st.column_config.TextColumn("Effort"),
                "iacMatch": st.column_config.TextColumn("IaC match"),
                "status": st.column_config.TextColumn("Status"),
                "verifiedResult": st.column_config.TextColumn("Verified result"),
                "realisedMonthly": st.column_config.NumberColumn("Realised / mo", format=money),
                "prUrl": st.column_config.LinkColumn("PR", display_text="Open PR"),
            }
            if view["prUrl"].notna().any():
                columns.append("prUrl")
            shown = view[columns].reset_index(drop=True)
            event = st.dataframe(
                shown,
                width="stretch",
                hide_index=True,
                column_config=column_config,
                on_select="rerun",
                selection_mode="single-row",
                key="findings_table",
            )
            st.caption("Select a row to open its evidence and details.")
            selected = event.selection.rows
            selected_id = shown.iloc[selected[0]]["id"] if selected else None

            if selected_id is not None and finding_dialog is not None:
                # Open once per new selection; closing the dialog doesn't rerun, so without this
                # guard every later widget interaction would pop it open again.
                opened = (run_name, selected_id)
                if st.session_state.get("_dialog_opened") != opened:
                    st.session_state["_dialog_opened"] = opened
                    finding_dialog(selected_id)
                elif st.button(
                    f"Open details for {selected_id}", icon=":material/open_in_new:"
                ):
                    finding_dialog(selected_id)
            elif selected_id is not None:
                with st.expander(f"Details for {selected_id}", expanded=True):
                    render_finding(selected_id)
            else:
                st.session_state.pop("_dialog_opened", None)

            with st.expander("Or pick a finding by id"):
                fid = st.selectbox("Finding", view["id"].tolist())
                if st.button("Show details", icon=":material/visibility:") and fid:
                    if finding_dialog is not None:
                        finding_dialog(fid)
                    else:
                        render_finding(fid)
    else:
        empty_state(
            "Finding-level detail is on the Engineering view",
            "Switch the “View for” control at the top of the page to Engineering for the findings "
            "table and per-finding evidence.",
            ":material/engineering:",
        )

# --------------------------------------------------------------------- KPIs & Trends tab
with tab_kpis:
    tagging_target = T.TAGGING_TARGET
    if kpis is None:
        empty_state(
            "No KPI set generated for this run yet",
            "Run `python scripts/kpis.py .finops/runs/<id>/ --runs-dir .finops/runs`, "
            "then reload.",
            ":material/analytics:",
        )
    else:
        k = kpis["kpis"]
        cards: list[dict] = []

        tc = k["taggingCompliance"]
        tagging_target = tc.get("target") or T.TAGGING_TARGET
        tc_val = f"{tc['value']:.1f}%" if tc["value"] is not None else "—"
        if tc["value"] is None:
            tc_delta = None
        elif tc.get("meetsTarget"):
            tc_delta = f"meets {tagging_target:g}% target"
        else:
            tc_delta = f"below {tagging_target:g}% target"
        cards.append(
            {
                "label": "Tagging compliance",
                "value": tc_val,
                "delta": tc_delta,
                "help": tc.get("note"),
                "history": spark("taggingCompliance"),
                "note": ":material/info: Approximate — an upper bound; see notes below."
                if is_approximate(tc)
                else None,
            }
        )

        ac = k["allocationCoverage"]
        cards.append(
            {
                "label": "Allocation coverage",
                "value": f"{ac['value']:.1f}%" if ac["value"] is not None else "—",
                "help": ac.get("note"),
                "history": spark("allocationCoverage"),
                "note": ":material/info: Approximate — see notes below."
                if is_approximate(ac)
                else None,
            }
        )

        es = k["estimatedSavingsOpportunity"]
        cards.append(
            {
                "label": "Est. savings opportunity",
                "value": f"{es['currency']} {es['value']:,.2f}",
                "help": es.get("note"),
                "history": spark("estimatedSavingsOpportunity"),
            }
        )

        rr = k["realisedSavingsRate"]
        cards.append(
            {
                "label": "Realised savings rate",
                "value": f"{rr['value']:.1f}%",
                "help": rr.get("note"),
                "history": spark("realisedSavingsRate"),
            }
        )

        an = k["anomalyCount"]
        cards.append(
            {
                "label": "Anomaly count",
                "value": an["value"],
                "delta": an["trend"] if an["trend"] != "unavailable" else None,
                "help": an.get("note"),
                "history": spark("anomalyCount"),
            }
        )

        # .get(..., {}) guards against older kpis.json reports generated before unitEconomics
        # existed -- same "degrade gracefully" pattern as the `kpis is None` branch above.
        ue = k.get("unitEconomics", {})
        has_ue = ue.get("value") is not None
        cards.append(
            {
                "label": "Unit economics",
                "value": f"{ue['value']:,.4f} {ue['unit']}" if has_ue else "—",
                "delta": ue.get("method") if has_ue else None,
                "help": ue.get("note"),
            }
        )
        card_grid(cards, per_row=T.KPI_PER_ROW)

        with st.expander("What do these mean / why unavailable?"):
            for name, kpi in k.items():
                note = kpi.get("note", "")
                st.markdown(f"**{KPI_NOTE_LABELS.get(name, name)}** — {md_escape(note)}")

    st.subheader("Trend across runs")
    metric_key = st.selectbox(
        "Metric", list(KPI_METRIC_LABELS), format_func=lambda k: KPI_METRIC_LABELS[k]
    )
    trend_df = history_all[metric_key]
    available_df = trend_df[trend_df["available"]]
    if available_df.empty:
        empty_state(
            "No runs with this KPI computed yet",
            "Run `python scripts/kpis.py .finops/runs/<id>/ --runs-dir .finops/runs` for each "
            "run you want on the trend.",
            ":material/show_chart:",
        )
    else:
        with st.container(border=True):
            chart(
                trend_chart(
                    available_df,
                    list(trend_df["runId"]),
                    KPI_METRIC_LABELS[metric_key],
                    target=tagging_target if metric_key == "taggingCompliance" else None,
                    mode=mode,
                )
            )
        missing = len(trend_df) - len(available_df)
        if missing:
            st.caption(f"{missing} run(s) omitted — this KPI wasn't computed for them.")

    # Compare with another run — tells a repeat scan apart from real progress
    other_runs = [p.name for p in runs if p.name != run_name]
    st.subheader("Compare with another run")
    if not other_runs:
        empty_state(
            "Only one run so far",
            "Run another audit (see docs/scheduling-recurring-runs.md) to compare what was "
            "resolved, recurring or new.",
            ":material/compare_arrows:",
        )
    else:
        compare_name = st.selectbox(
            "Compare against",
            other_runs,
            index=0,
            help=(
                "Findings are matched by (type, resourceId), not by id — ids are only stable "
                "within a single run."
            ),
        )
        compare_findings = load_run(RUNS_DIR / compare_name)["findings"]
        # Treat the earlier run (by folder-name sort order, the yyyymmdd-hhmm timestamp) as "a"
        # and the later run as "b", regardless of which one is currently selected above.
        earlier, later = sorted([(compare_name, compare_findings), (run_name, findings)])
        diff = compare_runs(earlier[1], later[1])
        card_grid(
            [
                {"label": "Resolved since earlier run", "value": len(diff["resolved"])},
                {"label": "Still recurring", "value": len(diff["recurring"])},
                {"label": "New this run", "value": len(diff["new"])},
            ],
            per_row=3,
        )
        st.caption(f"Earlier run: {md_escape(earlier[0])} · Later run: {md_escape(later[0])}")
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
                st.caption("None — nothing from the earlier run has been resolved yet.")
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
                st.caption("None — no finding is open in both runs.")
