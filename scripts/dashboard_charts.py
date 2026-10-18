"""Altair chart builders for the finops-squad dashboard.

Every chart shares one height, direct value labels instead of legends, and compact numbers.
Builders take plain DataFrames and return Altair charts -- no Streamlit, no I/O.
"""
from __future__ import annotations

import altair as alt
import pandas as pd

import dashboard_theme as T
from dashboard_helpers import compact_number


def _with_labels(df: pd.DataFrame, value: str, decimals: int = 2) -> pd.DataFrame:
    out = df.copy()
    out["label"] = out[value].map(lambda v: compact_number(v, decimals))
    return out


def hbar_chart(
    df: pd.DataFrame, category: str, value: str, tooltip: list[str], mode: str = "light"
) -> alt.Chart:
    """Horizontal bars sorted descending; the top item is emphasised, the rest muted."""
    data = _with_labels(df.sort_values(value, ascending=False), value)
    order = list(data[category])
    top = order[0] if order else None
    base = alt.Chart(data).encode(
        y=alt.Y(f"{category}:N", sort=order, title=None, axis=alt.Axis(labelLimit=260)),
        x=alt.X(f"{value}:Q", axis=None),
    )
    bars = base.mark_bar(color=T.ACCENT).encode(
        opacity=alt.condition(
            alt.datum[category] == top, alt.value(1.0), alt.value(T.MUTED_OPACITY)
        ),
        tooltip=tooltip,
    )
    labels = base.mark_text(align="left", dx=4, color=T.TEXT_COLORS[mode]).encode(text="label:N")
    height = max(T.CHART_HEIGHT // 2, T.BAR_ROW_HEIGHT * len(data))
    return (bars + labels).properties(height=min(height, T.CHART_HEIGHT * 2))


def vbar_chart(
    df: pd.DataFrame,
    category: str,
    value: str,
    order: list[str],
    color_map: dict[str, str] | None = None,
    tooltip: list[str] | None = None,
    mode: str = "light",
    decimals: int = 2,
) -> alt.Chart:
    """Vertical bars in a fixed category order, labelled on top. `color_map` colours per category
    (the category text stays on the axis, so colour is never the only signal)."""
    data = _with_labels(df, value, decimals)
    base = alt.Chart(data).encode(
        x=alt.X(f"{category}:N", sort=order, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(f"{value}:Q", axis=None),
    )
    if color_map:
        color = alt.Color(
            f"{category}:N",
            scale=alt.Scale(domain=list(color_map), range=list(color_map.values())),
            legend=None,
        )
        bars = base.mark_bar(size=T.BAR_WIDTH).encode(color=color, tooltip=tooltip or [category, value])
    else:
        bars = base.mark_bar(color=T.ACCENT, size=T.BAR_WIDTH).encode(
            tooltip=tooltip or [category, value]
        )
    labels = base.mark_text(dy=-8, color=T.TEXT_COLORS[mode]).encode(text="label:N")
    return (bars + labels).properties(height=T.CHART_HEIGHT)


def trend_chart(
    df: pd.DataFrame,
    run_order: list[str],
    title: str,
    target: float | None = None,
    mode: str = "light",
) -> alt.Chart:
    """Run-over-run line with the latest value labelled; optional dashed target rule."""
    data = _with_labels(df, "value")
    base = alt.Chart(data).encode(
        x=alt.X("runId:N", sort=run_order, title=None, axis=alt.Axis(labelAngle=-30)),
        y=alt.Y("value:Q", title=title, scale=alt.Scale(zero=True)),
    )
    line = base.mark_line(point=True, color=T.ACCENT).encode(tooltip=["runId", "value"])
    layers = [line]
    last = data.tail(1)
    if not last.empty:
        layers.append(
            alt.Chart(last)
            .mark_text(dy=-12, color=T.TEXT_COLORS[mode])
            .encode(x=alt.X("runId:N", sort=run_order), y="value:Q", text="label:N")
        )
    if target is not None:
        rule_df = pd.DataFrame({"target": [target], "text": [f"{target:g}% target"]})
        layers.append(
            alt.Chart(rule_df)
            .mark_rule(strokeDash=[6, 4], color=T.WARNING, strokeWidth=2)
            .encode(y="target:Q", tooltip=["text"])
        )
        layers.append(
            alt.Chart(rule_df)
            .mark_text(align="left", dy=-8, dx=4, color=T.WARNING)
            .encode(y="target:Q", text="text:N", x=alt.value(4))
        )
    return alt.layer(*layers).properties(height=T.TREND_HEIGHT)


def month_line_chart(df: pd.DataFrame, title: str, mode: str = "light") -> alt.Chart:
    """Monthly spend line (the fallback when a run has totalByMonth but no byService)."""
    data = _with_labels(df, "amount")
    base = alt.Chart(data).encode(
        x=alt.X("month:O", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("amount:Q", title=title),
    )
    line = base.mark_line(point=True, color=T.ACCENT).encode(tooltip=["month", "amount"])
    labels = base.mark_text(dy=-12, color=T.TEXT_COLORS[mode]).encode(text="label:N")
    return (line + labels).properties(height=T.CHART_HEIGHT)
