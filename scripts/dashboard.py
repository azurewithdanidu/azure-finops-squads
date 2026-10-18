#!/usr/bin/env python3
"""finops-squad dashboard — interactive visualizer for run artifacts.

Run with:
    streamlit run scripts/dashboard.py

Two views of the same run data, chosen with the persona control (and `?view=` in the URL):

- Executive   (dashboard_exec.py) — one plain-English page: headline, four KPI cards, top cost
  drivers, decisions needed, goal progress and a "how reliable are these numbers?" note.
- Engineering (dashboard_eng.py)  — Work queue / Spend / Governance / History & data quality,
  with finding-level evidence, blockers and next steps.

The Executive view reflects the FinOps Framework's Leadership persona; the Engineering view its
practitioner persona. Both build every number from the same helpers (dashboard_helpers.py and
dashboard_insights.py), so they cannot disagree.

Links: `?view=executive|engineering&run=<run id>` opens a specific view of a specific run.

Everything is read-only. The dashboard never calls Azure and never mutates artifacts. Pure/IO
helpers live outside this file so they can be unit-tested without a Streamlit runtime — see
tests/test_scripts.py. Artifact text is untrusted: it is rendered through native components only
(no raw HTML) and Markdown-escaped via dashboard_helpers.md_escape.
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

import dashboard_insights as I
import dashboard_theme as T
from dashboard_eng import render_engineering
from dashboard_exec import render_executive
from dashboard_helpers import (
    findings_dataframe,
    kpi_trend_dataframe,
    load_findings,
    load_iteration,
    load_json,
    load_kpis,
    load_verifications,
    md_escape,
    run_fingerprint,
    short_id,
    list_runs as _list_runs,
)
from dashboard_ui import KPI_METRIC_LABELS, RunContext, empty_state, theme_mode

REPO = Path(__file__).resolve().parent.parent
# FINOPS_RUNS_DIR lets tests (and unusual layouts) point the dashboard at another runs folder.
RUNS_DIR = Path(os.environ.get("FINOPS_RUNS_DIR") or REPO / ".finops" / "runs")
CONFIG_PATH = RUNS_DIR.parent / "config.json"

PERSONAS = ["Engineering", "Executive"]
VIEW_PARAMS = {"engineering": "Engineering", "executive": "Executive"}
PERSONA_HELP = (
    "Executive is for the FinOps Framework's Leadership persona: one plain-English page with the "
    "headline, KPIs, biggest cost drivers and decisions needed. Engineering is for practitioners: "
    "the work queue, finding-level evidence, spend, governance and data quality. Both show the "
    "same underlying numbers."
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
        "inventory": load_json(run / "inventory.json"),
        "texts": {
            "executive_summary": I.read_text_file(run / "reports" / "executive-summary.md"),
            "engineer_backlog": I.read_text_file(run / "reports" / "engineer-backlog.md"),
            "run_status": I.read_text_file(run / "run-status.md"),
        },
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

# Seed the controls from the URL (?view=executive|engineering&run=<id>) on a session's first
# load; Engineering and the newest run are the defaults. Invalid values are ignored.
run_names = [p.name for p in runs]
if st.session_state.get("run_name") not in run_names:
    qp_run = st.query_params.get("run")
    st.session_state["run_name"] = qp_run if qp_run in run_names else run_names[0]
if "persona" not in st.session_state:
    qp_view = str(st.query_params.get("view", "")).lower()
    st.session_state["persona"] = VIEW_PARAMS.get(qp_view, PERSONAS[0])

run_name = head_run.selectbox("Run", run_names, key="run_name")
persona = (
    head_persona.segmented_control("View for", PERSONAS, key="persona", help=PERSONA_HELP)
    or PERSONAS[0]  # deselecting the control falls back to the default view
)
# Keep the URL in sync so the current view can be shared as a link.
st.query_params["view"] = persona.lower()
st.query_params["run"] = run_name
run = RUNS_DIR / run_name

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
        "the per-currency breakdown for the rest. Totals are never summed across currencies.",
        icon=":material/warning:",
    )

# Savings numbers for BOTH views come from the same helpers (bucket_totals / realised_by_currency),
# so the Executive headline and the Engineering cards can never disagree.
totals = ledger.get("totals", {})
buckets = I.bucket_totals(df)
est = (
    I.estimated_total(buckets[currency])
    if currency in buckets
    else float(totals.get("estimatedMonthly", 0.0))
)
real = I.realised_by_currency(df).get(currency, float(totals.get("realisedMonthly", 0.0)))

oldest_first = sorted(runs, key=lambda p: p.name)
ctx = RunContext(
    runs_dir=RUNS_DIR,
    runs=runs,
    run=run,
    run_name=run_name,
    config=config,
    spend=spend,
    ledger=ledger,
    findings=findings,
    verifs=verifs,
    iteration=iteration,
    kpis=kpis,
    inventory=data["inventory"],
    texts=data["texts"],
    df=df,
    currency=currency,
    mixed_currencies=mixed_currencies,
    totals=totals,
    est=est,
    real=real,
    buckets=buckets,
    history=_kpi_history(tuple(str(p) for p in oldest_first), _kpis_fingerprint(oldest_first)),
    mode=mode,
    load_run=load_run,
)

if persona == "Executive":
    render_executive(ctx)
else:
    render_engineering(ctx)
