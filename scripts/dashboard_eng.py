"""Engineering view: the work queue and the evidence behind every number.

Tabs: Work queue (default) / Spend / Governance / History & data quality. Numbers come from the
same helpers as the Executive view (dashboard_helpers / dashboard_insights).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import dashboard_insights as I
import dashboard_theme as T
from dashboard_charts import hbar_chart, month_line_chart, trend_chart, vbar_chart
from dashboard_helpers import (
    BUCKET_LABELS,
    BUCKETS,
    STATUS_ORDER,
    TIER_ORDER,
    compare_runs,
    confidence_label,
    is_approximate,
    md_escape,
    money_format,
    safe_url,
)
from dashboard_ui import (
    KPI_METRIC_LABELS,
    KPI_NOTE_LABELS,
    RunContext,
    card_grid,
    chart,
    empty_state,
)


# ------------------------------------------------------------------------ finding detail
def render_finding(ctx: RunContext, fid: str) -> None:
    """Structured detail for one finding: summary, facts, blocker/next step, evidence, JSON."""
    f = next((x for x in ctx.findings if x.get("id") == fid), None)
    rows = ctx.df[ctx.df["id"] == fid]
    if f is None or rows.empty:
        empty_state("Finding not found", "Select another row in the work queue.")
        return
    row = rows.iloc[0]
    tier = f.get("tier")
    st.markdown(f"#### {md_escape(row['typeLabel'])} · {md_escape(fid)}")
    st.markdown(md_escape(f.get("summary")) or "_No summary recorded._")

    cur = md_escape(row["currency"])
    facts = [
        ("Risk tier", T.TIER_LABELS.get(tier, tier or "—")),
        ("Action bucket", BUCKET_LABELS[row["bucket"]]),
        ("Est. saving / mo", f"{cur} {row['estimatedMonthly']:,.2f}"),
        ("Price basis", row["basis"] or "—"),
        ("Confidence", confidence_label(row["confidence"])),
        ("Effort", row["effort"] or "—"),
        ("IaC match", row["iacMatch"] or "—"),
        ("Status", row["status"] or "—"),
        ("Realised / mo", f"{cur} {row['realisedMonthly']:,.2f}"),
    ]
    st.markdown("##### Key facts")
    for start in range(0, len(facts), 3):
        for col, (label, value) in zip(st.columns(3), facts[start : start + 3]):
            with col.container(border=True):
                st.caption(label)
                st.markdown(f"**{md_escape(value)}**")

    blocker, next_step = I.blocker_and_next_step(f, row["bucket"])
    with st.container(border=True):
        st.markdown(f"**What blocks this:** {md_escape(blocker)}")
        st.markdown(f"**Next step:** {md_escape(next_step)}")

    st.caption("Resource")
    st.code(str(f.get("resourceId") or "—"), language=None, wrap_lines=True)
    portal = I.portal_url(f.get("resourceId"))
    link_cols = st.columns(2)
    if portal:
        link_cols[0].link_button("Open in Azure Portal", portal, icon=":material/open_in_new:")
    pr = safe_url(f.get("prUrl"))
    if pr:
        link_cols[1].link_button("Open pull request", pr, icon=":material/call_merge:")

    st.markdown("##### Evidence")
    evidence = [e for e in (f.get("evidence") or []) if isinstance(e, dict)]
    if not evidence:
        empty_state("No evidence recorded", "Every finding should cite evidence — re-run the Analyser.")
    for ev in evidence:
        with st.container(border=True):
            st.markdown(f"**{md_escape(ev.get('capability', 'evidence'))}**")
            st.caption(f"Window: {md_escape(ev.get('timeWindow', '—'))}")
            st.markdown(md_escape(ev.get("observation")))
            if ev.get("tool"):
                st.caption("Tool")
                st.code(str(ev["tool"]), language=None, wrap_lines=True)
            if ev.get("query"):
                st.caption("Query")
                st.code(str(ev["query"]), language=None, wrap_lines=True)

    with st.expander("Raw JSON"):
        st.json(f)


if hasattr(st, "dialog"):

    @st.dialog("Finding details", width="large")
    def finding_dialog(ctx: RunContext, fid: str) -> None:
        render_finding(ctx, fid)

else:
    finding_dialog = None


# -------------------------------------------------------------------------- Work queue tab
def _work_queue(ctx: RunContext) -> None:
    df = ctx.df
    card_grid(
        [
            {"label": "Estimated saving / mo", "value": f"{ctx.currency} {ctx.est:,.2f}"},
            {"label": "Realised saving / mo", "value": f"{ctx.currency} {ctx.real:,.2f}"},
            {"label": "Findings", "value": int(ctx.totals.get("findingCount", len(df)))},
            {"label": "Verified", "value": int(ctx.totals.get("verifiedCount", 0))},
        ],
        per_row=4,
    )
    if ctx.real == 0 and ctx.est > 0:
        st.info(
            f"Realised saving is **{md_escape(ctx.currency)} 0.00** — nothing has been remediated "
            "and verified yet. Estimates are never counted as realised.",
            icon=":material/info:",
        )
    if ctx.mixed_currencies:
        st.subheader("Savings by currency")
        rows = [
            {
                "currency": c,
                "estimatedMonthly": v["totals"]["estimatedMonthly"],
                "realisedMonthly": v["totals"]["realisedMonthly"],
                "findingCount": v["totals"]["findingCount"],
            }
            for c, v in sorted(ctx.ledger.get("byCurrency", {}).items())
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

    st.subheader("Work queue")
    if df.empty:
        empty_state(
            "No findings in this run yet",
            "Ask the Analyser to run a mode (waste, rightsizing, tagging, …) and reload.",
        )
        return

    primary = ctx.buckets.get(ctx.currency, {})
    if primary:
        st.caption(
            f"Estimated per month in {ctx.currency}: "
            + " · ".join(f"{BUCKET_LABELS[k]} {v['amount']:,.2f}" for k, v in primary.items())
        )
    counts = df["bucket"].value_counts()
    chosen = st.pills(
        "Action bucket",
        BUCKETS,
        selection_mode="multi",
        default=BUCKETS,
        key="bucket_filter",
        format_func=lambda b: f"{BUCKET_LABELS[b]} ({int(counts.get(b, 0))})",
    )
    view = df[df["bucket"].isin(chosen or [])].copy()
    view = view.sort_values(["estimatedMonthly"], ascending=False)
    view["tierLabel"] = view["tier"].map(T.TIER_LABELS).fillna(view["tier"])
    view["bucketLabel"] = view["bucket"].map(BUCKET_LABELS)
    view["confidenceLabel"] = view["confidence"].map(confidence_label)
    row_mixed = ctx.mixed_currencies or df["currency"].nunique() > 1
    money = money_format(ctx.currency, row_mixed)

    if view.empty:
        empty_state(
            "No findings in the selected buckets",
            "Select at least one action bucket above to see findings again.",
            ":material/filter_alt_off:",
        )
    else:
        columns = ["id", "typeLabel", "tierLabel", "bucketLabel", "estimatedMonthly"]
        if row_mixed:
            columns.append("currency")
        columns += ["confidenceLabel", "effort", "iacMatch", "status"]
        if view["prUrl"].notna().any():
            columns.append("prUrl")
        column_config = {
            "id": st.column_config.TextColumn("ID", width="small"),
            "typeLabel": st.column_config.TextColumn("Finding"),
            "tierLabel": st.column_config.TextColumn("Risk tier"),
            "bucketLabel": st.column_config.TextColumn("Action bucket"),
            "estimatedMonthly": st.column_config.NumberColumn("Est. saving / mo", format=money),
            "currency": st.column_config.TextColumn("Currency", width="small"),
            "confidenceLabel": st.column_config.TextColumn("Confidence"),
            "effort": st.column_config.TextColumn("Effort"),
            "iacMatch": st.column_config.TextColumn("IaC match"),
            "status": st.column_config.TextColumn("Status"),
            "prUrl": st.column_config.LinkColumn("PR", display_text="Open PR"),
        }
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
        st.caption("Select a row to open its evidence, blocker and next step.")
        selected = event.selection.rows
        selected_id = shown.iloc[selected[0]]["id"] if selected else None

        if selected_id is not None and finding_dialog is not None:
            # Open once per new selection; closing the dialog doesn't rerun, so without this
            # guard every later widget interaction would pop it open again.
            opened = (ctx.run_name, selected_id)
            if st.session_state.get("_dialog_opened") != opened:
                st.session_state["_dialog_opened"] = opened
                finding_dialog(ctx, selected_id)
            elif st.button(f"Open details for {selected_id}", icon=":material/open_in_new:"):
                finding_dialog(ctx, selected_id)
        elif selected_id is not None:
            with st.expander(f"Details for {selected_id}", expanded=True):
                render_finding(ctx, selected_id)
        else:
            st.session_state.pop("_dialog_opened", None)

        with st.expander("Or pick a finding by id"):
            fid = st.selectbox("Finding", view["id"].tolist())
            if st.button("Show details", icon=":material/visibility:") and fid:
                if finding_dialog is not None:
                    finding_dialog(ctx, fid)
                else:
                    render_finding(ctx, fid)

    backlog = ctx.texts.get("engineer_backlog")
    if backlog:
        with st.expander("Engineer backlog report"):
            st.markdown(backlog)  # Markdown only: raw HTML is not rendered


# ------------------------------------------------------------------------------ Spend tab
def _spend(ctx: RunContext) -> None:
    spend = ctx.spend
    spend_currency = spend.get("currency", ctx.currency)
    if spend_currency != ctx.currency and str(spend.get("status", "")).lower() == "available":
        st.caption(
            f"Spend is reported in **{md_escape(spend_currency)}** (the subscription's billing "
            f"currency), which may differ from the report default ({md_escape(ctx.currency)}). "
            "Figures are shown as returned, not converted."
        )
    if str(spend.get("status", "")).lower() == "unavailable":
        st.warning(
            "**Spend data unavailable** — "
            + md_escape(spend.get("reason", "cost.query_spend backend not connected.")),
            icon=":material/cloud_off:",
        )
        return

    by_service = spend.get("byService")
    has_service = (
        isinstance(by_service, list)
        and by_service
        and all(isinstance(r, dict) and "cost" in r for r in by_service)
    )
    if has_service:
        sp = pd.DataFrame(by_service).sort_values("cost", ascending=False)
        total = I.spend_total(spend)
        start, end, _ = I.spend_window(spend)
        card_grid(
            [
                {
                    "label": f"Total spend ({spend.get('timeframe', 'period')})",
                    "value": f"{spend_currency} {total:,.2f}",
                    "note": f"Window: {I.window_label(start, end)}" if start and end else None,
                }
            ],
            per_row=3,
        )
        with st.container(border=True):
            st.subheader("By service")
            st.caption(f"Top 15 services by cost ({spend_currency})")
            chart(hbar_chart(sp.head(15), "service", "cost", ["service", "cost"], ctx.mode))
            for r in by_service:
                if r.get("note"):
                    st.caption(f"**{md_escape(r.get('service'))}** — {md_escape(r['note'])}")
    elif spend.get("totalByMonth"):
        sp = pd.DataFrame(
            [{"month": m, "amount": v} for m, v in spend["totalByMonth"].items()]
        ).sort_values("month")
        with st.container(border=True):
            st.subheader("By month")
            chart(month_line_chart(sp, f"Spend ({spend_currency})", ctx.mode))
    else:
        empty_state(
            "No spend breakdown for this run",
            "Run Discovery with a connected cost backend to capture spend by service.",
            ":material/query_stats:",
        )

    by_rg = spend.get("byResourceGroupTop10")
    if isinstance(by_rg, list) and by_rg and all(isinstance(r, dict) and "cost" in r for r in by_rg):
        with st.container(border=True):
            st.subheader("By resource group")
            st.caption(f"Top {len(by_rg)} resource groups by cost ({spend_currency})")
            chart(
                hbar_chart(
                    pd.DataFrame(by_rg), "resourceGroup", "cost", ["resourceGroup", "cost"], ctx.mode
                )
            )
    else:
        st.caption("No resource-group breakdown was captured for this run.")

    caveats = [
        ("Currency", spend.get("currencyNote")),
        ("Source", (spend.get("source") or {}).get("note")),
        ("Query", f"{spend.get('groupBy', '—')} · {spend.get('metric', '—')} · "
                  f"{spend.get('granularity', '—')}"),
    ]
    with st.expander("Window and source caveats"):
        for label, text in caveats:
            if text:
                st.markdown(f"**{label}** — {md_escape(text)}")


# -------------------------------------------------------------------------- Governance tab
def _governance(ctx: RunContext) -> None:
    required = I.required_tags(ctx.kpis, ctx.config)
    st.subheader("Tag coverage")
    st.caption("Required tags: " + ", ".join(md_escape(t) for t in required))
    rows = I.tag_coverage_rows(ctx.inventory, required)
    if rows:
        with st.container(border=True):
            st.caption("Share of resources that have each required tag (%)")
            tdf = pd.DataFrame(rows).rename(columns={"tag": "tagName"})
            chart(
                hbar_chart(tdf, "tagName", "coverage", ["tagName", "missing", "total", "coverage"], ctx.mode)
            )
            st.caption(
                "Each bar is exact for that one tag. Overall compliance (all required tags "
                "together) can be lower — see History & data quality."
            )
    else:
        empty_state(
            "No tag coverage data for this run",
            "Re-run Discovery with the tag-coverage query so inventory.json carries tagCoverage.",
            ":material/sell:",
        )

    if ctx.iteration:
        st.subheader("Iteration progress")
        it, window = ctx.iteration, ctx.iteration.get("measurementWindow", {})
        st.caption(
            f"**{md_escape(it.get('iterationId', 'unnamed iteration'))}** · "
            f"window {md_escape(window.get('from', '?'))} → {md_escape(window.get('to', '?'))} · "
            f"status: {md_escape(it.get('status', 'in-progress'))}"
        )
        if it.get("constraints"):
            st.caption("Guardrails: " + md_escape("; ".join(it["constraints"])))
        goals = it.get("goals", [])
        if goals:
            goal_rows = []
            for g in goals:
                baseline, target = g.get("baseline", {}), g.get("target", {})
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

    df = ctx.df
    if df.empty:
        return
    st.subheader("Findings overview")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.markdown("**Estimated vs realised**")
            st.caption(f"{ctx.currency} per month — estimates are never counted as realised")
            comp = pd.DataFrame(
                {"kind": ["Estimated", "Realised"], "amount": [ctx.est, ctx.real]}
            )
            chart(
                vbar_chart(
                    comp, "kind", "amount", ["Estimated", "Realised"],
                    {"Estimated": T.ESTIMATED, "Realised": T.REALISED}, mode=ctx.mode,
                )
            )
    with right:
        with st.container(border=True):
            st.markdown("**Estimated saving by type**")
            # Never blend currencies: in a mixed-currency run chart only the primary currency.
            src = df[df["currency"] == ctx.currency] if ctx.mixed_currencies else df
            st.caption(f"{ctx.currency}/mo" + (" — primary currency only" if ctx.mixed_currencies else ""))
            by_type = (
                src.groupby("typeLabel", as_index=False)["estimatedMonthly"]
                .sum()
                .sort_values("estimatedMonthly", ascending=False)
            )
            chart(hbar_chart(by_type, "typeLabel", "estimatedMonthly", ["typeLabel", "estimatedMonthly"], ctx.mode))

    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.markdown("**Findings by risk tier**")
            st.caption("Number of findings; tier shown as text and colour")
            by_tier = df.groupby("tier", as_index=False).size().rename(columns={"size": "count"})
            by_tier["tierLabel"] = by_tier["tier"].map(T.TIER_LABELS).fillna(by_tier["tier"])
            chart(
                vbar_chart(
                    by_tier, "tierLabel", "count", [T.TIER_LABELS[t] for t in TIER_ORDER],
                    {T.TIER_LABELS[t]: c for t, c in T.TIER_COLORS.items()},
                    tooltip=["tierLabel", "count"], mode=ctx.mode, decimals=0,
                )
            )
    with right:
        with st.container(border=True):
            st.markdown("**Status funnel**")
            by_status = df.groupby("status", as_index=False).size().rename(columns={"size": "count"})
            chart(
                vbar_chart(
                    by_status, "status", "count", STATUS_ORDER,
                    tooltip=["status", "count"], mode=ctx.mode, decimals=0,
                )
            )


# --------------------------------------------------------------- History & data quality tab
def _kpi_cards(ctx: RunContext) -> float:
    """Render the KPI card grid; returns the tagging target for the trend chart."""
    target = T.TAGGING_TARGET
    if ctx.kpis is None:
        empty_state(
            "No KPI set generated for this run yet",
            "Run `python scripts/kpis.py .finops/runs/<id>/ --runs-dir .finops/runs`, then reload.",
            ":material/analytics:",
        )
        return target
    k = ctx.kpis["kpis"]
    cards: list[dict] = []

    tc = k["taggingCompliance"]
    target = tc.get("target") or T.TAGGING_TARGET
    if tc["value"] is None:
        tc_delta = None
    elif tc.get("meetsTarget"):
        tc_delta = f"meets {target:g}% target"
    else:
        tc_delta = f"below {target:g}% target"
    cards.append(
        {
            "label": "Tagging compliance",
            "value": f"{tc['value']:.1f}%" if tc["value"] is not None else "—",
            "delta": tc_delta,
            "help": tc.get("note"),
            "history": ctx.spark("taggingCompliance"),
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
            "history": ctx.spark("allocationCoverage"),
            "note": ":material/info: Approximate — see notes below." if is_approximate(ac) else None,
        }
    )
    es = k["estimatedSavingsOpportunity"]
    cards.append(
        {
            "label": "Est. savings opportunity",
            "value": f"{es['currency']} {es['value']:,.2f}",
            "help": es.get("note"),
            "history": ctx.spark("estimatedSavingsOpportunity"),
        }
    )
    rr = k["realisedSavingsRate"]
    cards.append(
        {
            "label": "Realised savings rate",
            "value": f"{rr['value']:.1f}%",
            "help": rr.get("note"),
            "history": ctx.spark("realisedSavingsRate"),
        }
    )
    an = k["anomalyCount"]
    cards.append(
        {
            "label": "Anomaly count",
            "value": an["value"],
            "delta": an["trend"] if an["trend"] != "unavailable" else None,
            "help": an.get("note"),
            "history": ctx.spark("anomalyCount"),
        }
    )
    # .get(..., {}) guards against older kpis.json reports generated before unitEconomics existed.
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
    return target


def _artifacts(ctx: RunContext) -> None:
    st.subheader("Artifacts per run")
    rows = []
    for run in sorted(ctx.runs, key=lambda p: p.name, reverse=True):
        row = {"run": run.name}
        row.update({k: "Yes" if ok else "Missing" for k, ok in I.artifact_checklist(run).items()})
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.caption("Missing artifacts mean the matching view or KPI is blank for that run.")


def _history(ctx: RunContext) -> None:
    target = _kpi_cards(ctx)

    if ctx.kpis is not None:
        with st.expander("KPI methods and notes (including why something is unavailable)"):
            rows = [
                {
                    "KPI": KPI_NOTE_LABELS.get(name, name),
                    "value": kpi.get("value"),
                    "method": kpi.get("method"),
                    "note": kpi.get("note"),
                }
                for name, kpi in ctx.kpis["kpis"].items()
            ]
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.subheader("Trend across runs")
    metric_key = st.selectbox(
        "Metric", list(KPI_METRIC_LABELS), format_func=lambda k: KPI_METRIC_LABELS[k]
    )
    trend_df = ctx.history[metric_key]
    available_df = trend_df[trend_df["available"]]
    if available_df.empty:
        empty_state(
            "No runs with this KPI computed yet",
            "Run `python scripts/kpis.py .finops/runs/<id>/ --runs-dir .finops/runs` for each run "
            "you want on the trend.",
            ":material/show_chart:",
        )
    else:
        with st.container(border=True):
            chart(
                trend_chart(
                    available_df,
                    list(trend_df["runId"]),
                    KPI_METRIC_LABELS[metric_key],
                    target=target if metric_key == "taggingCompliance" else None,
                    mode=ctx.mode,
                )
            )
        missing = len(trend_df) - len(available_df)
        if missing:
            st.caption(f"{missing} run(s) omitted — this KPI wasn't computed for them.")

    st.subheader("Compare with another run")
    other_runs = [p.name for p in ctx.runs if p.name != ctx.run_name]
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
            help="Findings are matched by (type, resourceId), not by id — ids are only stable "
            "within a single run.",
        )
        compare_findings = ctx.load_run(ctx.runs_dir / compare_name)["findings"]
        # The earlier run (folder-name sort order = yyyymmdd-hhmm) is "a", the later "b".
        earlier, later = sorted([(compare_name, compare_findings), (ctx.run_name, ctx.findings)])
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
                            {"type": f.get("type"), "resourceId": f.get("resourceId"),
                             "summary": f.get("summary")}
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
                            {"id": f.get("id"), "type": f.get("type"), "tier": f.get("tier"),
                             "resourceId": f.get("resourceId"), "status": f.get("status")}
                            for f in diff["recurring"]
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.caption("None — no finding is open in both runs.")

    status_md = ctx.texts.get("run_status")
    if status_md:
        with st.expander("Run status (run-status.md)"):
            st.markdown(status_md)  # Markdown only: raw HTML is not rendered
    _artifacts(ctx)


# --------------------------------------------------------------------------------- entry
def render_engineering(ctx: RunContext) -> None:
    tab_queue, tab_spend, tab_gov, tab_hist = st.tabs(
        [
            ":material/inbox: Work queue",
            ":material/payments: Spend",
            ":material/verified_user: Governance",
            ":material/history: History & data quality",
        ]
    )
    with tab_queue:
        _work_queue(ctx)
    with tab_spend:
        _spend(ctx)
    with tab_gov:
        _governance(ctx)
    with tab_hist:
        _history(ctx)
