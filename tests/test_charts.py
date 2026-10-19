"""Tests for the daily-spend chart builders (scripts/charts.py) and their insight helpers.

Offline-verified only: built from fixtures, not from real Cost Management output.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import charts as C  # noqa: E402
import dashboard_insights as I  # noqa: E402
import spend_daily as sd  # noqa: E402
import spend_events as se  # noqa: E402

PERSONA_RUN = REPO / "tests" / "fixtures" / "persona_runs" / "20260101-0000"


@pytest.fixture(scope="module")
def spend():
    return json.loads((PERSONA_RUN / "spend.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def daily(spend):
    return sd.get_daily(spend)


@pytest.fixture(scope="module")
def events(spend):
    return se.detect_events(spend)["events"]


def _ev(date, kind="stopped", before=10.0, after=0.0, source="detected", service="A", note=None):
    e = {"date": date, "service": service, "kind": kind, "before": before, "after": after,
         "currency": "USD", "source": source}
    if note:
        e["note"] = note
    return e


def _spec_text(chart) -> str:
    return json.dumps(chart.to_dict())


# --------------------------------------------------------------------------- frames
def test_charts_module_has_no_streamlit_import():
    source = (REPO / "scripts" / "charts.py").read_text(encoding="utf-8")
    assert "import streamlit" not in source and "from streamlit" not in source


def test_series_colors_fixed_grey_for_other_and_distinct_otherwise():
    order = [f"s{i}" for i in range(10)] + ["Other"]
    colors = C.series_colors(order)
    assert colors[-1] == C.T.OTHER_COLOR
    assert len(set(colors[:-1])) == 10 and C.T.OTHER_COLOR not in colors[:-1]


def test_daily_frame_zero_fills_flags_provisional_and_orders(daily):
    df, order = C.daily_frame(daily)
    assert order[0] == "Azure Firewall" and order[-1] == "DNS"
    assert len(df) == 30 * 6  # every service for every day
    gateway = df[df["service"] == "Application Gateway"].sort_values("date")
    assert gateway.iloc[-1]["cost"] == 0.0  # stopped services are explicit zeros, not gaps
    assert int(df[df["service"] == "Storage"]["provisional"].sum()) == 3
    assert df[df["provisional"]]["date"].min() == pd.Timestamp("2025-12-29")
    only, only_order = C.daily_frame(daily, ["Storage"])
    assert only_order == ["Storage"] and set(only["service"]) == {"Storage"}
    none, none_order = C.daily_frame(daily, [])
    assert none.empty and none_order == []


def test_total_frame_rolling_mean_uses_settled_days_only(daily):
    totals = C.total_frame(daily)
    assert len(totals) == 30
    assert totals["rolling"].iloc[:6].isna().all()  # needs a full 7 days
    assert totals[totals["provisional"]]["rolling"].isna().all()
    assert not math.isnan(totals["rolling"].iloc[10])


# --------------------------------------------------------------------------- events
def test_label_planning_limits_staggers_and_prioritises():
    events = [
        _ev("2026-01-01", before=100, after=0),
        _ev("2026-01-02", before=50, after=0),
        _ev("2026-01-03", before=5, after=0),
        _ev("2026-01-04", before=2, after=0),
        _ev("2026-01-05", kind="manual", before=None, after=None, source="manual", note="Freeze"),
        _ev("2026-01-06", kind="iteration-start", before=None, after=None, source="iteration", note="q1 starts"),
    ]
    plan = C.plan_event_labels(events, max_labels=3, levels=3)
    labelled = [p for p in plan if p["labelled"]]
    assert len(labelled) == 3 and len(plan) == 6  # excess events stay in the plan, unlabelled
    assert {p["date"] for p in labelled} == {"2026-01-05", "2026-01-01", "2026-01-02"}  # manual first
    by_date = sorted(labelled, key=lambda p: p["date"])
    assert [p["level"] for p in by_date] == [0, 1, 2]  # neighbours sit in different lanes
    assert all(p["level"] == 0 for p in plan if not p["labelled"])
    assert not [p for p in C.plan_event_labels(events, max_labels=0) if p["labelled"]]
    assert C.plan_event_labels([]) == []


def test_exec_event_selection_caps_at_three_and_drops_iteration_boundaries():
    events = [
        _ev("2026-01-01", before=100, after=0),
        _ev("2026-01-02", before=50, after=0),
        _ev("2026-01-03", before=5, after=0),
        _ev("2026-01-04", before=60, after=10, kind="step-change"),
        _ev("2026-01-05", kind="iteration-start", before=None, after=None, source="iteration"),
        _ev("2026-01-09", kind="manual", before=None, after=None, source="manual", note="Freeze"),
    ]
    chosen = C.select_exec_events(events)
    assert len(chosen) == 3
    assert "iteration" not in {e["source"] for e in chosen}
    assert [e["date"] for e in chosen] == sorted(e["date"] for e in chosen)
    assert any(e["source"] == "manual" for e in chosen)  # the user's own note outranks detections
    assert C.select_exec_events(events, 1)[0]["source"] == "manual"
    assert C.select_exec_events([]) == []


def test_events_for_services_keeps_unscoped_events():
    events = [_ev("2026-01-01", service="A"), _ev("2026-01-02", service="B"),
              _ev("2026-01-03", service=None, kind="manual", source="manual", note="n")]
    kept = C.events_for_services(events, ["A"])
    assert [e["date"] for e in kept] == ["2026-01-01", "2026-01-03"]


def test_events_table_frame(events):
    df = C.events_table_frame(events)
    assert list(df.columns) == ["Date", "What happened", "Service", "Before / day", "After / day", "Currency", "Source"]
    assert df.iloc[0]["What happened"] == "Application Gateway charges stopped"
    assert C.events_table_frame([]).empty


def test_headroom_only_when_labels_are_needed(events):
    assert C.headroom(100, [], 6) == pytest.approx(105)
    assert C.headroom(100, events, 6) == pytest.approx(130)
    assert C.headroom(0, [], 6) == pytest.approx(1.05)


# --------------------------------------------------------------------------- charts
def test_stacked_area_chart_structure(daily, events):
    chart = C.stacked_area_chart(daily, events)
    spec = _spec_text(chart)
    assert '"stack": "zero"' in spec
    assert "Still settling" in spec  # the provisional band is labelled
    assert '"opacity": 0.35' in spec  # provisional days are lighter
    assert "Application Gateway charges stopped" in spec  # event label
    assert len(chart.to_dict()["layer"]) > len(C.stacked_area_chart(daily, []).to_dict()["layer"])
    assert C.T.CHART_HEIGHT == chart.to_dict()["height"]


def test_lines_chart_has_dashed_provisional_segments_and_rolling_mean(daily, events):
    spec = _spec_text(C.lines_chart(daily, events))
    assert '"strokeDash": [4, 3]' in spec
    assert "7-day mean" in spec
    no_mean = _spec_text(C.lines_chart(daily, events, show_total_mean=False))
    assert "7-day mean (total)" not in no_mean


def test_total_area_chart_labels_at_most_three_events(daily):
    many = [_ev(f"2025-12-{d:02d}", before=20 + d, after=0, service=f"S{d}") for d in range(3, 12)]
    chart = C.total_area_chart(daily, many)
    labels = [
        r["label"]
        for ds in chart.to_dict()["datasets"].values()
        for r in ds
        if isinstance(r, dict) and r.get("labelled") is True
    ]
    assert len(labels) == C.EXEC_EVENTS == 3
    # every shown event is still reachable by tooltip, and nothing beyond 3 is drawn at all
    rules = [r for ds in chart.to_dict()["datasets"].values() for r in ds if isinstance(r, dict) and "tip" in r]
    assert len(rules) == 3


def test_charts_build_for_every_selection_and_without_events(daily):
    for fn in (C.stacked_area_chart, C.lines_chart):
        for services in (None, ["Storage"], ["Other"], []):
            assert fn(daily, [], services).to_dict()["height"] == C.T.CHART_HEIGHT
    assert C.total_area_chart(daily, []).to_dict()


def test_charts_without_provisional_days(daily):
    clean = {**daily, "provisionalFrom": "2026-06-01"}  # beyond the window: nothing provisional
    assert "Still settling" not in _spec_text(C.total_area_chart(clean, []))
    assert C.stacked_area_chart(clean, []).to_dict()


def test_dark_theme_label_colour(daily, events):
    assert C.T.TEXT_COLORS["dark"] in _spec_text(C.stacked_area_chart(daily, events, theme="dark"))


# ------------------------------------------------------------------- insight helpers
def test_event_sentences_are_plain_english_with_currency_safe_amounts():
    stopped = I.event_sentence(_ev("2026-09-11", before=13.7, after=0.0, service="Application Gateway"))
    assert stopped == "11 Sep 2026 — Application Gateway charges stopped (it had been about USD 13.70 a day)"
    step = I.event_sentence(_ev("2026-01-05", kind="step-change", before=10.0, after=16.0))
    assert "charges rose" in step and "from about USD 10.00 to about USD 16.00 a day" in step
    assert "now about USD 20.00" in I.event_sentence(_ev("2026-01-05", kind="started", before=0, after=20.0))
    assert "one-day spike" in I.event_sentence(_ev("2026-01-05", kind="spike", before=10, after=40))
    manual = I.event_sentence(_ev("2026-01-05", kind="manual", before=None, after=None, source="manual", note="Freeze begins"))
    assert manual == "5 Jan 2026 — Freeze begins"


def test_reconcile_message(spend):
    assert I.reconcile_message(sd.reconcile(spend), "USD") is None
    bad = {**spend, "totalLastMonth": spend["totalLastMonth"] * 1.1}
    level, text = I.reconcile_message(sd.reconcile(bad), "USD")
    assert level == "warning" and "add up to" in text and "tolerance" in text
    level, text = I.reconcile_message(sd.reconcile({**spend, "to": "2026-01-15"}), "USD")
    assert level == "info" and "not checked" in text
    assert I.reconcile_message(sd.reconcile({}), "USD") is None  # no daily data: nothing to say
