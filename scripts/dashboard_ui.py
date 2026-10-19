"""Shared Streamlit components and the loaded-run context used by both dashboard views."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pandas as pd
import streamlit as st

# unitEconomics is intentionally excluded from the trend labels: its unit/method can differ
# run-to-run (azure-openai-tokens vs manual-denominator vs unavailable), so a single trend line
# would compare incompatible numbers. It's still shown as a headline card, just not trended.
KPI_METRIC_LABELS = {
    "estimatedSavingsOpportunity": "Estimated savings opportunity",
    "realisedSavingsRate": "Realised savings rate (%)",
    "taggingCompliance": "Tagging compliance (%)",
    "allocationCoverage": "Allocation coverage (%)",
    "anomalyCount": "Anomaly count",
}
# A superset that also labels unitEconomics for the explainer notes.
KPI_NOTE_LABELS = {**KPI_METRIC_LABELS, "unitEconomics": "Unit economics"}


@dataclass
class RunContext:
    """Everything a view needs about the selected run, loaded once and shared by both views."""

    runs_dir: Path
    runs: list[Path]
    run: Path
    run_name: str
    config: dict
    spend: dict
    ledger: dict
    findings: list[dict]
    verifs: dict
    iteration: dict | None
    kpis: dict | None
    inventory: dict | None
    texts: dict  # Markdown artifacts: executive_summary, engineer_backlog, run_status (str | None)
    df: pd.DataFrame
    currency: str  # primary (most findings) savings currency
    mixed_currencies: bool
    totals: dict
    est: float  # estimated monthly saving, primary currency
    real: float  # realised monthly saving, primary currency
    buckets: dict  # dashboard_insights.bucket_totals(df)
    history: dict  # kpi trend DataFrames, all runs oldest-first
    mode: str  # "light" | "dark"
    load_run: Callable[[Path], dict] = field(repr=False, default=lambda p: {})

    def spark(self, metric_key: str) -> list[float]:
        """KPI history up to and including the selected run, oldest first."""
        h = self.history[metric_key]
        h = h[(h["runId"] <= self.run_name) & h["available"]]
        return [float(v) for v in h["value"]]


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
