"""Executive view: one page, plain English, no raw tables.

Deliberately omits finding ids, tier codes, IaC details, resource ids, status funnels, run
comparison tables and raw JSON -- those live in the Engineering view. Numbers come from the same
helpers as the Engineering view (dashboard_helpers / dashboard_insights).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import charts
import dashboard_insights as I
import spend_daily as sd
from dashboard_charts import hbar_chart
from dashboard_helpers import is_approximate, md_escape
from dashboard_ui import KPI_NOTE_LABELS, RunContext, card_grid, chart, empty_state

TOP_DRIVERS = 5


def _headline(ctx: RunContext) -> None:
    text = I.build_headline(ctx.spend, ctx.buckets, I.realised_by_currency(ctx.df), ctx.currency)
    with st.container(border=True):
        st.markdown(md_escape(text))


def _kpi_cards(ctx: RunContext) -> None:
    spend, cur = ctx.spend, ctx.currency
    spend_cur = spend.get("currency") or cur
    total = I.spend_total(spend)
    _, end, days = I.spend_window(spend)
    rate = I.monthly_run_rate(total, days)
    if rate is not None:
        run_rate = {
            "label": "Monthly spend run-rate",
            "value": I.money_text(spend_cur, rate),
            "note": f"Average over the {days} days to {I.pretty_date(end)}.",
        }
    elif total is not None:
        run_rate = {
            "label": "Spend in period",
            "value": I.money_text(spend_cur, total),
            "note": "The dates of the spend window weren't recorded.",
        }
    else:
        run_rate = {
            "label": "Monthly spend run-rate",
            "value": "—",
            "note": "Spend data isn't available for this run.",
        }

    b = ctx.buckets.get(cur)
    split = (
        "  \n".join(  # each line escaped separately: "$" in amounts would start LaTeX
            md_escape(f"{I.EXEC_BUCKET_LABELS[k]}: {I.money_text(cur, v['amount'])}")
            for k, v in b.items()
            if v["amount"] > 0 or k in ("ready", "blocked_iac", "decision")
        )
        if b
        else "No findings yet."
    )
    opportunity = {
        "label": "Estimated monthly opportunity",
        "value": I.money_text(cur, ctx.est),
        "note": split,
        "history": ctx.spark("estimatedSavingsOpportunity"),
    }
    realised = {
        "label": "Realised monthly savings",
        "value": I.money_text(cur, ctx.real),
        "note": "Only counts changes that were merged and verified.",
    }

    tag = {"label": "Tag compliance", "value": "—", "note": "No KPI set for this run yet."}
    tc = ((ctx.kpis or {}).get("kpis") or {}).get("taggingCompliance")
    if tc and tc.get("value") is not None:
        target = tc.get("target") or 90
        verdict = "Meets" if tc.get("meetsTarget") else "Below"
        caveat = (
            " This is a rough upper estimate — the real figure is probably lower."
            if is_approximate(tc)
            else ""
        )
        tag = {
            "label": "Tag compliance",
            "value": f"{tc['value']:.1f}%",
            "note": f"{verdict} the {target:g}% target.{caveat}",
            "history": ctx.spark("taggingCompliance"),
        }
    elif tc:
        tag["note"] = "Not available this run."
    card_grid([run_rate, opportunity, realised, tag], per_row=2)


def _timeline(ctx: RunContext) -> None:
    st.subheader("Spend over time")
    daily = sd.get_daily(ctx.spend)
    if daily is None:
        empty_state(
            "Daily data not captured — re-run Discovery",
            "The spend timeline needs a daily cost series (spend.json `daily`). Ask the "
            "Orchestrator to re-run Discovery; it makes one extra Daily-grain cost query.",
            ":material/show_chart:",
        )
        return
    shown = charts.select_exec_events(ctx.events.get("events", []))
    with st.container(border=True):
        st.caption(
            f"Total cost per day ({daily.get('currency') or ctx.spend.get('currency') or ''}). "
            "The last three days are still settling and may change."
        )
        chart(charts.total_area_chart(daily, shown, theme=ctx.mode))
        for e in shown:
            st.markdown("- " + md_escape(I.event_sentence(e)))
        note = I.reconcile_message(sd.reconcile(ctx.spend), daily.get("currency"))
        if note:
            st.caption(md_escape(note[1]))


def _cost_drivers(ctx: RunContext) -> None:
    st.subheader("Biggest cost drivers")
    rows = ctx.spend.get("byService")
    usable = (
        isinstance(rows, list)
        and rows
        and all(isinstance(r, dict) and "cost" in r and "service" in r for r in rows)
    )
    if not usable:
        empty_state(
            "No spend breakdown for this run",
            "Run Discovery with a connected cost backend to see where the money goes.",
            ":material/query_stats:",
        )
        return
    top = sorted(rows, key=lambda r: r["cost"], reverse=True)[:TOP_DRIVERS]
    cur = ctx.spend.get("currency") or ctx.currency
    with st.container(border=True):
        st.caption(f"Top {len(top)} services by cost ({cur}), whole spend window")
        chart(
            hbar_chart(
                pd.DataFrame(top)[["service", "cost"]],
                "service",
                "cost",
                ["service", "cost"],
                ctx.mode,
            )
        )
        for r in top:
            if r.get("note"):
                st.caption(f"**{md_escape(r['service'])}** — {md_escape(r['note'])}")


def _decisions(ctx: RunContext) -> None:
    st.subheader("Decisions needed")
    rows = ctx.df[ctx.df["bucket"] == "decision"] if not ctx.df.empty else ctx.df
    if rows.empty:
        empty_state(
            "No decisions are waiting",
            "Nothing needs an owner's call right now.",
            ":material/task_alt:",
        )
        return
    for _, r in rows.sort_values("estimatedMonthly", ascending=False).iterrows():
        with st.container(border=True):
            st.markdown(f"**{md_escape(r['typeLabel'])}**")
            st.markdown(md_escape(I.lead_sentence(r["summary"])))
            amount = (
                "Estimated saving: **"
                + md_escape(I.money_text(r["currency"], r["estimatedMonthly"]))
                + " a month**"
                if r["estimatedMonthly"] > 0
                else "Estimated saving: **not quantified**"
            )
            st.caption(f"{amount} · Confidence: **{I.confidence_words(r['confidence'])}**")


def _progress(ctx: RunContext) -> None:
    if not ctx.iteration:
        return
    st.subheader("Progress against goals")
    goals = ctx.iteration.get("goals") or []
    if not goals:
        empty_state(
            "No goals recorded yet",
            "Add goals to this run's iteration brief to track progress here.",
            ":material/flag:",
        )
        return
    for g in goals:
        fraction = I.goal_progress(g)
        facts = (
            f"Baseline {md_escape(I.goal_value_text(g.get('baseline')))} · "
            f"now {md_escape(I.goal_value_text(g.get('current') or g.get('baseline')))} · "
            f"target {md_escape(I.goal_value_text(g.get('target')))}"
        )
        with st.container(border=True):
            st.markdown(md_escape(g.get("description", "Goal")))
            if fraction is None:
                st.caption(facts + " — progress can't be shown as a percentage.")
            else:
                st.progress(fraction, text=f"{fraction:.0%} of the way · {facts}")


def _reliability(ctx: RunContext) -> None:
    with st.expander("How reliable are these numbers?"):
        for note in I.reliability_notes(
            ctx.spend, ctx.kpis, ctx.config, ctx.currency, ctx.mixed_currencies, KPI_NOTE_LABELS
        ):
            st.markdown("- " + md_escape(note))


def _summary_report(ctx: RunContext) -> None:
    text = ctx.texts.get("executive_summary")
    if not text:
        return
    with st.expander("Executive summary report"):
        st.markdown(text)  # Markdown only: raw HTML is not rendered
    st.download_button(
        "Download executive summary",
        text,
        file_name=f"executive-summary-{ctx.run_name}.md",
        mime="text/markdown",
        icon=":material/download:",
    )


def render_executive(ctx: RunContext) -> None:
    _headline(ctx)
    _kpi_cards(ctx)
    _timeline(ctx)
    _cost_drivers(ctx)
    _decisions(ctx)
    _progress(ctx)
    _reliability(ctx)
    _summary_report(ctx)
