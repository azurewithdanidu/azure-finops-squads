"""Altair chart builders for the daily spend series and its events (no Streamlit imports).

- stacked_area_chart: top services plus "Other", stacked.
- lines_chart: one line per service plus the 7-day rolling mean of the total.
- total_area_chart: the all-services daily total (Executive view).

All three draw the provisional days (the last three, still settling) dashed/lighter inside a shaded
"Still settling" band, and mark events as dashed rules with staggered labels; events beyond the
label limit stay in the tooltip. Data comes from `spend.daily` via `spend_daily`; nothing here
fabricates values, and money stays in the series' single currency.
"""
from __future__ import annotations

import altair as alt
import pandas as pd

import dashboard_theme as T
import spend_daily as sd
from spend_events import describe_event, event_magnitude

LABEL_LEVELS = 3  # vertical lanes for staggered event labels
MAX_LABELS = 6
EXEC_EVENTS = 3
ROLLING_DAYS = 7
SETTLING_TEXT = "Still settling"


# ------------------------------------------------------------------------------- frames
def series_colors(order: list[str]) -> list[str]:
    """One colour per service in `order`; 'Other' is always the fixed grey."""
    palette = iter(T.SERIES_PALETTE)
    return [T.OTHER_COLOR if s == sd.OTHER else next(palette, T.OTHER_COLOR) for s in order]


def daily_frame(daily: dict, services: list[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Long frame (date, service, cost, rank, provisional), every day zero-filled, plus the
    service order (largest first, 'Other' last) restricted to `services` when given."""
    order = [s for s in sd.service_order(daily) if services is None or s in services]
    by_service = sd.series_by_service(daily)
    prov = sd.provisional_from(daily)
    rows = [
        {
            "date": pd.Timestamp(d),
            "service": s,
            "cost": by_service[s].get(d, 0.0),
            "rank": rank,
            "provisional": d >= prov,
        }
        for rank, s in enumerate(order)
        for d in sd.all_dates(daily)
    ]
    return pd.DataFrame(rows, columns=["date", "service", "cost", "rank", "provisional"]), order


def total_frame(daily: dict) -> pd.DataFrame:
    """Daily total with a 7-day rolling mean computed over SETTLED days only."""
    prov = sd.provisional_from(daily)
    totals = sd.total_by_date(daily)
    df = pd.DataFrame(
        [{"date": pd.Timestamp(d), "cost": c, "provisional": d >= prov} for d, c in sorted(totals.items())],
        columns=["date", "cost", "provisional"],
    )
    settled_cost = df["cost"].where(~df["provisional"])
    df["rolling"] = settled_cost.rolling(ROLLING_DAYS, min_periods=ROLLING_DAYS).mean()
    return df


def _with_bridge(df: pd.DataFrame, group: str | None) -> pd.DataFrame:
    """Provisional rows plus the last settled row of each series, so dashed segments connect."""
    if df.empty:
        return df
    settled = df[~df["provisional"]]
    prov = df[df["provisional"]]
    if settled.empty or prov.empty:
        return prov
    keys = [group] if group else []
    last = settled.sort_values("date").groupby(keys).tail(1) if keys else settled.tail(1)
    return pd.concat([last.assign(provisional=True), prov], ignore_index=True)


# ------------------------------------------------------------------------------- events
def plan_event_labels(events: list[dict], max_labels: int = MAX_LABELS, levels: int = LABEL_LEVELS) -> list[dict]:
    """Choose which events get an on-chart label and stagger them over `levels` lanes.

    Manual events rank first, then detected ones by size of change, then iteration boundaries.
    The top `max_labels` get `labelled: True` and a lane (cycling in date order so neighbours sit
    at different heights); the rest stay `labelled: False` (rule + tooltip only).
    """

    def priority(item):
        i, e = item
        group = 0 if e.get("source") == "manual" else 2 if e.get("source") == "iteration" else 1
        return (group, -event_magnitude(e), e["date"], i)

    ranked = sorted(enumerate(events), key=priority)
    chosen = {i for i, _ in ranked[: max(0, max_labels)]}
    planned = [{**e, "labelled": i in chosen, "level": 0} for i, e in enumerate(events)]
    lane = 0
    for e in sorted((p for p in planned if p["labelled"]), key=lambda p: p["date"]):
        e["level"] = lane % levels
        lane += 1
    return planned


def select_exec_events(events: list[dict], n: int = EXEC_EVENTS) -> list[dict]:
    """At most `n` events for the Executive view: manual notes first, then the biggest detected
    changes; iteration boundaries are left out. Returned in date order."""
    candidates = [e for e in events if e.get("source") != "iteration"]
    candidates.sort(
        key=lambda e: (0 if e.get("source") == "manual" else 1, -event_magnitude(e), e["date"])
    )
    return sorted(candidates[:n], key=lambda e: (e["date"], e.get("service") or ""))


def events_for_services(events: list[dict], services: list[str]) -> list[dict]:
    """Events for the selected services (plus those not tied to a service)."""
    return [e for e in events if not e.get("service") or e["service"] in services]


def events_table_frame(events: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Date": e["date"],
                "What happened": describe_event(e),
                "Service": e.get("service") or "—",
                "Before / day": e.get("before"),
                "After / day": e.get("after"),
                "Currency": e.get("currency") or "—",
                "Source": e.get("source"),
            }
            for e in events
        ],
        columns=["Date", "What happened", "Service", "Before / day", "After / day", "Currency", "Source"],
    )


def _tooltip_text(e: dict) -> str:
    text = f"{e['date']}: {describe_event(e)}"
    if e.get("before") is not None and e.get("after") is not None:
        text += f" ({e['before']:,.2f} → {e['after']:,.2f} {e.get('currency') or ''} a day)".replace("  ", " ")
    return text


def headroom(y_max: float, events: list[dict], max_labels: int = MAX_LABELS) -> float:
    """Top of the y axis: extra blank room above the data when event labels need a lane."""
    labelled = any(e["labelled"] for e in plan_event_labels(events, max_labels))
    return (y_max or 1.0) * (1.3 if labelled else 1.05)


def event_layers(
    events: list[dict],
    y_top: float,
    last_day: pd.Timestamp,
    first_day: pd.Timestamp,
    y_title: str,
    theme: str = "light",
    max_labels: int = MAX_LABELS,
) -> list[alt.Chart]:
    """Rules (with tooltips) for every event plus staggered labels for the top `max_labels`,
    placed in the blank band between the data and `y_top`."""
    planned = plan_event_labels(events, max_labels)
    if not planned:
        return []
    span = max((last_day - first_day).days, 1)
    rows = [
        {
            "date": pd.Timestamp(e["date"]),
            "label": describe_event(e),
            "tip": _tooltip_text(e),
            "y": y_top * (1 - 0.08 * e["level"]),
            "labelled": e["labelled"],
            "late": (pd.Timestamp(e["date"]) - first_day).days / span > 0.7,
        }
        for e in planned
    ]
    df = pd.DataFrame(rows)
    color = T.TEXT_COLORS[theme]
    rules = (
        alt.Chart(df)
        .mark_rule(strokeDash=[4, 3], color=T.WARNING, opacity=0.8, strokeWidth=1.5)
        .encode(
            x=alt.X("date:T"),
            tooltip=[alt.Tooltip("date:T", format="%d %b %Y", title="Date"), alt.Tooltip("tip:N", title="Event")],
        )
    )
    layers = [rules]
    for late, align, dx in ((False, "left", 4), (True, "right", -4)):
        part = df[df["labelled"] & (df["late"] == late)]
        if not part.empty:
            layers.append(
                alt.Chart(part)
                .mark_text(align=align, dx=dx, baseline="top", fontSize=T.LABEL_FONT_SIZE - 1, color=color)
                .encode(x="date:T", y=alt.Y("y:Q", title=y_title), text="label:N")
            )
    return layers


def settling_layers(daily: dict, y_title: str, theme: str = "light") -> list[alt.Chart]:
    """A shaded 'Still settling' band over the provisional days."""
    prov, end = sd.provisional_from(daily), sd.window(daily)[1]
    if prov > end:
        return []
    band = pd.DataFrame(
        {"start": [pd.Timestamp(prov)], "end": [pd.Timestamp(end) + pd.Timedelta(days=1)], "text": [SETTLING_TEXT]}
    )
    rect = alt.Chart(band).mark_rect(color=T.ESTIMATED, opacity=0.12).encode(x="start:T", x2="end:T")
    label = (
        alt.Chart(band)
        .mark_text(align="right", baseline="top", dx=-4, fontSize=T.LABEL_FONT_SIZE - 1, color=T.TEXT_COLORS[theme], opacity=0.75)
        .encode(x="start:T", y=alt.value(4), text="text:N")
    )
    return [rect, label]


def _x_axis() -> alt.X:
    return alt.X("date:T", title=None, axis=alt.Axis(format="%d %b", labelOverlap=True, tickCount=8))


def _finish(layers: list[alt.Chart]) -> alt.LayerChart:
    return alt.layer(*layers).properties(height=T.CHART_HEIGHT)


# ------------------------------------------------------------------------------- charts
def stacked_area_chart(
    daily: dict,
    events: list[dict] | None = None,
    services: list[str] | None = None,
    theme: str = "light",
    max_labels: int = MAX_LABELS,
) -> alt.LayerChart:
    df, order = daily_frame(daily, services)
    cur = daily.get("currency") or ""
    title = f"Daily cost ({cur})" if cur else "Daily cost"
    color = alt.Color(
        "service:N",
        sort=order,
        scale=alt.Scale(domain=order, range=series_colors(order)),
        legend=alt.Legend(orient="bottom", title=None),
    )
    no_legend = color.copy(deep=True)
    no_legend.legend = None
    first, last = pd.Timestamp(sd.window(daily)[0]), pd.Timestamp(sd.window(daily)[1])
    y_max = float(df.groupby("date")["cost"].sum().max()) if not df.empty else 1.0
    y_top = headroom(y_max, events or [], max_labels)
    y = alt.Y("cost:Q", stack="zero", title=title, scale=alt.Scale(domain=[0, y_top], nice=False))
    tip = [
        alt.Tooltip("date:T", format="%d %b %Y", title="Date"),
        alt.Tooltip("service:N", title="Service"),
        alt.Tooltip("cost:Q", format=",.2f", title="Cost"),
    ]
    order_enc = alt.Order("rank:Q", sort="descending")
    settled = df[~df["provisional"]]
    layers = [*settling_layers(daily, title, theme)]
    layers.append(
        alt.Chart(settled).mark_area().encode(x=_x_axis(), y=y, color=color, order=order_enc, tooltip=tip)
    )
    prov = _with_bridge(df, "service")
    if not prov.empty:
        layers.append(
            alt.Chart(prov).mark_area(opacity=0.35).encode(x=_x_axis(), y=y, color=no_legend, order=order_enc, tooltip=tip)
        )
    layers += event_layers(events or [], y_top, last, first, title, theme, max_labels)
    return _finish(layers)


def lines_chart(
    daily: dict,
    events: list[dict] | None = None,
    services: list[str] | None = None,
    theme: str = "light",
    max_labels: int = MAX_LABELS,
    show_total_mean: bool = True,
) -> alt.LayerChart:
    df, order = daily_frame(daily, services)
    cur = daily.get("currency") or ""
    title = f"Daily cost ({cur})" if cur else "Daily cost"
    color = alt.Color(
        "service:N",
        sort=order,
        scale=alt.Scale(domain=order, range=series_colors(order)),
        legend=alt.Legend(orient="bottom", title=None),
    )
    no_legend = color.copy(deep=True)
    no_legend.legend = None
    y_max = float(df["cost"].max()) if not df.empty else 1.0
    rolled = total_frame(daily).dropna(subset=["rolling"]) if show_total_mean else pd.DataFrame()
    if not rolled.empty:
        y_max = max(y_max, float(rolled["rolling"].max()))
    y_top = headroom(y_max, events or [], max_labels)
    y = alt.Y("cost:Q", title=title, scale=alt.Scale(domain=[0, y_top], nice=False))
    tip = [
        alt.Tooltip("date:T", format="%d %b %Y", title="Date"),
        alt.Tooltip("service:N", title="Service"),
        alt.Tooltip("cost:Q", format=",.2f", title="Cost"),
    ]
    layers = [*settling_layers(daily, title, theme)]
    layers.append(alt.Chart(df[~df["provisional"]]).mark_line().encode(x=_x_axis(), y=y, color=color, tooltip=tip))
    prov = _with_bridge(df, "service")
    if not prov.empty:
        layers.append(
            alt.Chart(prov).mark_line(strokeDash=[4, 3], opacity=0.5).encode(x=_x_axis(), y=y, color=no_legend, tooltip=tip)
        )
    if show_total_mean:
        mean_tip = [
            alt.Tooltip("date:T", format="%d %b %Y", title="Date"),
            alt.Tooltip("rolling:Q", format=",.2f", title=f"{ROLLING_DAYS}-day mean of total"),
        ]
        layers.append(
            alt.Chart(rolled)
            .mark_line(strokeWidth=3.5, color=T.TEXT_COLORS[theme], opacity=0.85)
            .encode(x=_x_axis(), y=alt.Y("rolling:Q", title=title, scale=alt.Scale(domain=[0, y_top], nice=False)), tooltip=mean_tip)
        )
        if not rolled.empty:
            layers.append(
                alt.Chart(rolled.tail(1).assign(text=f"{ROLLING_DAYS}-day mean (total)"))
                .mark_text(align="right", baseline="bottom", dy=-6, fontSize=T.LABEL_FONT_SIZE - 1, color=T.TEXT_COLORS[theme])
                .encode(x="date:T", y=alt.Y("rolling:Q", title=title, scale=alt.Scale(domain=[0, y_top], nice=False)), text="text:N")
            )
    first, last = pd.Timestamp(sd.window(daily)[0]), pd.Timestamp(sd.window(daily)[1])
    layers += event_layers(events or [], y_top, last, first, title, theme, max_labels)
    return _finish(layers)


def total_area_chart(
    daily: dict,
    events: list[dict] | None = None,
    theme: str = "light",
    max_labels: int = EXEC_EVENTS,
) -> alt.LayerChart:
    """Executive view: the all-services daily total as one area, with at most a few events."""
    totals = total_frame(daily)
    cur = daily.get("currency") or ""
    title = f"Daily cost ({cur})" if cur else "Daily cost"
    shown = select_exec_events(events or [], max_labels)
    y_max = float(totals["cost"].max()) if not totals.empty else 1.0
    y_top = headroom(y_max, shown, max_labels)
    y = alt.Y("cost:Q", title=title, scale=alt.Scale(domain=[0, y_top], nice=False))
    tip = [
        alt.Tooltip("date:T", format="%d %b %Y", title="Date"),
        alt.Tooltip("cost:Q", format=",.2f", title="Total cost"),
    ]
    layers = [*settling_layers(daily, title, theme)]
    layers.append(
        alt.Chart(totals[~totals["provisional"]])
        .mark_area(color=T.ACCENT, opacity=0.85, line={"color": T.ACCENT})
        .encode(x=_x_axis(), y=y, tooltip=tip)
    )
    prov = _with_bridge(totals, None)
    if not prov.empty:
        layers.append(
            alt.Chart(prov)
            .mark_area(color=T.ACCENT, opacity=0.3, line={"color": T.ACCENT, "strokeDash": [4, 3]})
            .encode(x=_x_axis(), y=y, tooltip=tip)
        )
    first, last = pd.Timestamp(sd.window(daily)[0]), pd.Timestamp(sd.window(daily)[1])
    layers += event_layers(shown, y_top, last, first, title, theme, max_labels)
    return _finish(layers)
