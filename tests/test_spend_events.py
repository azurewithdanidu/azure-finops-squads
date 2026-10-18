"""Tests for spend event detection (scripts/spend_events.py).

Offline-verified only: the series are synthetic but shaped like the real cases — a service
billing ~$13.70/day that stops (the deleted Application Gateway), and a steady ~$42/day service
(Azure Firewall) that must produce NO event.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import spend_daily as sd  # noqa: E402
import spend_events as se  # noqa: E402

PERSONA_RUN = REPO / "tests" / "fixtures" / "persona_runs" / "20260101-0000"
START = date(2026, 1, 1)
NOISE = [0.3, -0.2, 0.4, -0.4, 0.1, -0.3, 0.2]  # deterministic jitter, well under any threshold


def make_spend(services: dict, days: int = 42, currency: str = "USD", provisional: int = 3) -> dict:
    """A spend.json with a daily block; `services` maps name -> f(day_index) -> cost."""
    series, totals = [], []
    for i in range(days):
        d = (START + timedelta(days=i)).isoformat()
        total = 0.0
        for name, fn in services.items():
            cost = round(fn(i), 4)
            if cost:
                series.append({"date": d, "service": name, "cost": cost})
            total += cost
        totals.append({"date": d, "cost": round(total, 4)})
    end = START + timedelta(days=days - 1)
    return {
        "status": "available", "currency": currency,
        "daily": {
            "granularity": "Daily", "currency": currency, "from": START.isoformat(),
            "to": end.isoformat(),
            "provisionalFrom": (end - timedelta(days=provisional - 1)).isoformat(),
            "series": series, "dailyTotal": totals,
        },
    }


def steady(level):
    return lambda i: level + NOISE[i % len(NOISE)]


def kinds(report):
    return [(e["service"], e["kind"], e["date"]) for e in report["events"]]


# --------------------------------------------------------------------------- stopped
def test_stopped_service_is_detected_on_the_first_zero_day():
    # ~$13.70/day for 21 days (to 21 Jan), then nothing.
    spend = make_spend({"Application Gateway": lambda i: 13.70 if i < 21 else 0.0})
    report = se.detect_events(spend)
    assert report["available"]
    assert kinds(report) == [("Application Gateway", "stopped", "2026-01-22")]
    ev = report["events"][0]
    assert ev["before"] == 13.7 and ev["after"] == 0.0
    assert ev["currency"] == "USD" and ev["source"] == "detected"
    assert se.describe_event(ev) == "Application Gateway charges stopped"


def test_steady_service_produces_no_event():
    spend = make_spend({"Azure Firewall": steady(42.0)})
    assert se.detect_events(spend)["events"] == []


def test_the_real_pair_yields_exactly_one_event():
    spend = make_spend(
        {"Azure Firewall": steady(42.0), "Application Gateway": lambda i: 13.70 if i < 21 else 0.0}
    )
    assert kinds(se.detect_events(spend)) == [("Application Gateway", "stopped", "2026-01-22")]


def test_stop_does_not_also_report_a_step_change_or_spike():
    spend = make_spend({"A": lambda i: 20.0 if i < 25 else 0.0}, days=45)
    assert [e["kind"] for e in se.detect_events(spend)["events"]] == ["stopped"]


def test_provisional_days_are_ignored():
    # Only the last 3 (provisional) days are zero: not a stop yet.
    spend = make_spend({"A": lambda i: 13.7 if i < 39 else 0.0})
    assert se.detect_events(spend)["events"] == []
    # Two settled zero days + three provisional zero days is still < 3 settled zero days.
    spend = make_spend({"A": lambda i: 13.7 if i < 37 else 0.0})
    assert se.detect_events(spend)["events"] == []
    # Three settled zero days is enough.
    spend = make_spend({"A": lambda i: 13.7 if i < 36 else 0.0})
    assert [e["kind"] for e in se.detect_events(spend)["events"]] == ["stopped"]


def test_provisional_default_is_the_last_three_days_when_unrecorded():
    spend = make_spend({"A": lambda i: 13.7 if i < 36 else 0.0})
    del spend["daily"]["provisionalFrom"]
    assert [e["kind"] for e in se.detect_events(spend)["events"]] == ["stopped"]
    assert se.detect_events(spend)["settledThrough"] == "2026-02-08"


def test_needs_seven_days_of_prior_spend_to_count_as_stopped():
    spend = make_spend({"A": lambda i: 13.7 if 10 <= i < 15 else 0.0})  # only 5 days of spend
    found = [e["kind"] for e in se.detect_events(spend)["events"]]
    assert "stopped" not in found and found == ["started"]  # the earlier start is real


# --------------------------------------------------------------------------- started
def test_started_service():
    spend = make_spend({"New Service": lambda i: 0.0 if i < 12 else 20.0})
    report = se.detect_events(spend)
    assert kinds(report) == [("New Service", "started", "2026-01-13")]
    assert report["events"][0]["before"] == 0.0 and report["events"][0]["after"] == 20.0


def test_a_service_that_just_started_is_not_yet_confirmed():
    spend = make_spend({"New Service": lambda i: 0.0 if i < 37 else 20.0})  # 2 settled days only
    assert se.detect_events(spend)["events"] == []


# ----------------------------------------------------------------------- step-change
def test_sustained_step_change_up():
    spend = make_spend({"A": lambda i: 10.0 if i < 20 else 16.0})
    report = se.detect_events(spend)
    assert kinds(report) == [("A", "step-change", "2026-01-21")]
    assert report["events"][0]["before"] == 10.0 and report["events"][0]["after"] == 16.0
    assert se.describe_event(report["events"][0]) == "A charges rose"


def test_step_change_down_is_described_as_fell():
    spend = make_spend({"A": lambda i: 20.0 if i < 20 else 12.0})
    ev = se.detect_events(spend)["events"][0]
    assert ev["kind"] == "step-change" and se.describe_event(ev) == "A charges fell"


def test_small_shift_is_not_a_step_change():
    spend = make_spend({"A": lambda i: 10.0 if i < 20 else 12.0})  # +20% < 30%
    assert se.detect_events(spend)["events"] == []


def test_short_lived_shift_is_not_a_step_change():
    spend = make_spend({"A": lambda i: 16.0 if 20 <= i < 23 else 10.0})  # 3 days only
    kinds_found = [e["kind"] for e in se.detect_events(spend)["events"]]
    assert "step-change" not in kinds_found


# ----------------------------------------------------------------------------- spike
def test_spike_beyond_three_sigma_and_minimum_amount():
    spend = make_spend({"A": lambda i: 40.0 if i == 25 else steady(10.0)(i)})
    report = se.detect_events(spend)
    assert kinds(report) == [("A", "spike", "2026-01-26")]
    assert report["events"][0]["after"] == 40.0
    assert se.describe_event(report["events"][0]) == "A had a one-day spike"


def test_bump_below_the_minimum_amount_is_not_a_spike():
    spend = make_spend({"A": lambda i: 13.0 if i == 25 else 10.0})  # +3 < min_spike 5
    assert se.detect_events(spend)["events"] == []


def test_noisy_service_within_three_sigma_is_not_a_spike():
    noisy = [8, 12, 9, 11, 7, 13, 10, 12, 8, 11, 9, 10, 12, 8]
    spend = make_spend({"A": lambda i: noisy[i % len(noisy)] + (6 if i == 30 else 0)})
    assert [e for e in se.detect_events(spend)["events"] if e["kind"] == "spike"] == []


# ------------------------------------------------------------------------ materiality
def test_immaterial_service_is_ignored():
    spend = make_spend({"Tiny": lambda i: 0.4 if i < 21 else 0.0})  # below $1/day
    assert se.detect_events(spend)["events"] == []
    assert [e["kind"] for e in se.detect_events(spend, min_daily=0.1)["events"]] == ["stopped"]


def test_other_bucket_is_ignored():
    spend = make_spend({"Other": lambda i: 30.0 if i < 21 else 0.0})
    assert se.detect_events(spend)["events"] == []


# --------------------------------------------------- manual and iteration events
def test_manual_and_iteration_events():
    spend = make_spend({"A": steady(10.0)})
    iteration = {"iterationId": "q1", "measurementWindow": {"from": "2026-01-10", "to": "2026-03-01"}}
    manual = [
        {"date": "2026-01-15", "label": "Moved workload to the new region", "service": "A"},
        {"date": "2026-01-16", "note": "Freeze begins", "kind": "change-freeze"},
        {"date": "not a date", "label": "bad date"},
        {"date": "2026-01-17"},  # no label
        {"date": "2026-06-01", "label": "outside the window"},
        {"date": "2026-01-18", "label": "odd kind", "kind": "<script>"},
        "not an object",
    ]
    report = se.detect_events(spend, iteration, manual)
    by_source = {}
    for e in report["events"]:
        by_source.setdefault(e["source"], []).append(e)
    assert [e["kind"] for e in by_source["iteration"]] == ["iteration-start"]  # end is out of window
    assert by_source["iteration"][0]["note"] == "q1 starts"
    manual_kinds = sorted(e["kind"] for e in by_source["manual"])
    assert manual_kinds == ["change-freeze", "manual", "manual"]  # unsafe kind falls back
    assert len(report["warnings"]) == 4
    first = next(e for e in by_source["manual"] if e["service"] == "A")
    assert se.describe_event(first) == "Moved workload to the new region"
    assert report["events"] == sorted(
        report["events"], key=lambda e: (e["date"], e["service"] or "", e["kind"])
    )


def test_manual_event_text_is_length_capped():
    spend = make_spend({"A": steady(10.0)})
    report = se.detect_events(spend, None, [{"date": "2026-01-15", "label": "x" * 1000}])
    assert len(report["events"][0]["note"]) == se.MAX_NOTE


def test_events_file_loading(tmp_path):
    assert se.load_manual_events(None) == ([], [])
    assert se.load_manual_events(tmp_path / "missing.json") == ([], [])
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    assert se.load_manual_events(bad)[1]
    wrong = tmp_path / "wrong.json"
    wrong.write_text('{"events": 3}', encoding="utf-8")
    assert se.load_manual_events(wrong)[1]
    ok = tmp_path / "ok.json"
    ok.write_text('{"events": [{"date": "2026-01-15", "label": "x"}]}', encoding="utf-8")
    assert len(se.load_manual_events(ok)[0]) == 1


# --------------------------------------------------------------------- no data / helpers
def test_no_daily_series_gives_an_empty_unavailable_report():
    report = se.detect_events({"status": "available", "byService": [{"service": "A", "cost": 1}]})
    assert report["available"] is False and report["events"] == []
    assert se.detect_events({})["available"] is False


def test_event_magnitude_and_describe_fallbacks():
    assert se.event_magnitude({"before": 13.7, "after": 0.0}) == 13.7
    assert se.event_magnitude({"before": None, "after": None}) == 0.0
    assert se.describe_event({"kind": "started", "service": "X"}) == "X charges started"
    assert se.describe_event({"kind": "iteration-start", "note": "q1 starts"}) == "q1 starts"
    assert se.describe_event({"kind": "mystery"}) == "Event noted"


def test_the_persona_fixture_matches_the_real_case():
    spend = json.loads((PERSONA_RUN / "spend.json").read_text(encoding="utf-8"))
    report = se.detect_events(spend)
    assert kinds(report) == [("Application Gateway", "stopped", "2025-12-23")]


# --------------------------------------------------------------------------------- CLI
def test_cli_writes_the_report_and_is_deterministic(tmp_path, capsys):
    runs = tmp_path / ".finops" / "runs"
    run = runs / "20260101-0000"
    shutil.copytree(PERSONA_RUN, run)
    (run.parent.parent / "events.json").write_text(
        json.dumps([{"date": "2025-12-10", "label": "Migration weekend"}]), encoding="utf-8"
    )
    assert se.main(["spend_events.py", str(run)]) == 0
    out = run / "reports" / "spend-events.json"
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["runId"] == "20260101-0000" and doc["available"] is True
    assert [e["source"] for e in doc["events"]] == ["manual", "detected"]
    assert "Application Gateway charges stopped" in capsys.readouterr().out
    fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = se.build_report(run, run.parent.parent / "events.json", now=fixed)
    b = se.build_report(run, run.parent.parent / "events.json", now=fixed)
    assert a == b and a["generatedAt"] == "2026-01-01T00:00:00Z"


def test_cli_handles_missing_spend_and_missing_daily(tmp_path, capsys):
    assert se.main(["spend_events.py", str(tmp_path)]) == 1
    run = tmp_path / "r"
    run.mkdir()
    (run / "spend.json").write_text(json.dumps({"status": "available"}), encoding="utf-8")
    assert se.main(["spend_events.py", str(run)]) == 0
    doc = json.loads((run / "reports" / "spend-events.json").read_text(encoding="utf-8"))
    assert doc["available"] is False and doc["events"] == []
    assert "Re-run Discovery" in capsys.readouterr().out


def test_events_never_mix_currencies():
    spend = make_spend({"A": lambda i: 13.7 if i < 21 else 0.0}, currency="AUD")
    assert {e["currency"] for e in se.detect_events(spend)["events"]} == {"AUD"}
    assert sd.get_daily(spend)["currency"] == "AUD"
