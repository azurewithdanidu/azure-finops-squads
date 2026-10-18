"""AppTest smoke tests for the daily spend timeline in both dashboard personas.

Offline-verified only: runs against fixtures (tests/fixtures/persona_runs), not a real subscription.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

PERSONA_RUN = REPO / "tests" / "fixtures" / "persona_runs" / "20260101-0000"
EMPTY_STATE = "Daily data not captured — re-run Discovery"


def _app(monkeypatch, runs_dir, view):
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("FINOPS_RUNS_DIR", str(runs_dir))
    at = AppTest.from_file(str(REPO / "scripts" / "dashboard.py"), default_timeout=60)
    at.query_params["view"] = view
    return at.run()


def _text(node) -> str:
    parts = []
    for attr in ("value", "label", "body", "help"):
        v = getattr(node, attr, None)
        if isinstance(v, str):
            parts.append(v)
    for child in getattr(node, "children", {}).values():
        parts.append(_text(child))
    return "\n".join(parts)


def plain(text: str) -> str:
    """Markdown-unescape (the dashboard backslash-escapes untrusted text before rendering)."""
    return re.sub(r"\\(.)", r"\1", text)


@pytest.fixture
def make_runs(tmp_path):
    """Copy the fixture run into <tmp>/.finops/runs/, optionally editing its spend.json."""

    def build(edit=None, events=None):
        runs = tmp_path / ".finops" / "runs"
        run = runs / "20260101-0000"
        shutil.copytree(PERSONA_RUN, run)
        if edit:
            spend = json.loads((run / "spend.json").read_text(encoding="utf-8"))
            edit(spend)
            (run / "spend.json").write_text(json.dumps(spend), encoding="utf-8")
        if events is not None:
            (tmp_path / ".finops" / "events.json").write_text(json.dumps(events), encoding="utf-8")
        return runs

    return build


def _drop_daily(spend):
    spend.pop("daily")


# ------------------------------------------------------------------------ with daily
def test_executive_shows_the_timeline_with_a_plain_english_event(monkeypatch):
    at = _app(monkeypatch, PERSONA_RUN.parent, "executive")
    assert not at.exception
    text = plain(_text(at.main))
    assert any(h.value == "Spend over time" for h in at.subheader)
    assert "Application Gateway charges stopped (it had been about USD 14.29 a day)" in text
    assert "still settling" in text
    assert EMPTY_STATE not in text
    assert len(at.dataframe) == 0  # still no tables in the Executive view
    assert not re.search(r"\bT[0-3]\b", text)


def test_engineering_spend_tab_has_controls_and_events_table(monkeypatch):
    at = _app(monkeypatch, PERSONA_RUN.parent, "engineering")
    assert not at.exception
    assert any(h.value == "Daily spend" for h in at.subheader)
    assert [m.label for m in at.multiselect if m.label == "Services"]
    services = next(m for m in at.multiselect if m.label == "Services")
    assert "Azure Firewall" in services.options and services.value == services.options
    events_tables = [d for d in at.dataframe if "What happened" in list(d.value.columns)]
    assert len(events_tables) == 1
    assert events_table_has_gateway(events_tables[0])
    assert not [w for w in at.warning if "add up to" in w.value]  # reconciles cleanly


def events_table_has_gateway(table) -> bool:
    return "Application Gateway charges stopped" in set(table.value["What happened"])


def test_engineering_style_toggle_and_service_selection(monkeypatch):
    at = _app(monkeypatch, PERSONA_RUN.parent, "engineering")
    at.session_state["daily_style"] = "Lines"
    at.run()
    assert not at.exception
    at.session_state["daily_services"] = ["Storage"]
    at.run()
    assert not at.exception
    tables = [d for d in at.dataframe if "What happened" in list(d.value.columns)]
    assert tables == [] or "Application Gateway charges stopped" not in set(tables[0].value["What happened"])
    assert "No events detected" in _text(at.main)
    at.session_state["daily_services"] = []
    at.run()
    assert not at.exception and "No services selected" in _text(at.main)


def test_reconciliation_mismatch_warns_in_engineering_and_notes_in_executive(monkeypatch, make_runs):
    runs = make_runs(lambda s: s.update(totalLastMonth=s["totalLastMonth"] * 1.2))
    eng = _app(monkeypatch, runs, "engineering")
    assert not eng.exception
    assert any("add up to" in w.value and "tolerance" in w.value for w in eng.warning)
    exe = _app(monkeypatch, runs, "executive")
    assert not exe.exception and "add up to" in plain(_text(exe.main))


def test_truncated_series_is_flagged(monkeypatch, make_runs):
    runs = make_runs(lambda s: s["daily"].update(truncated=True))
    at = _app(monkeypatch, runs, "engineering")
    assert not at.exception
    assert any("row limit" in w.value for w in at.warning)


def test_manual_events_file_shows_up_in_both_views(monkeypatch, make_runs):
    runs = make_runs(events=[{"date": "2025-12-10", "label": "Migration weekend"}])
    exe = _app(monkeypatch, runs, "executive")
    assert not exe.exception and "10 Dec 2025 — Migration weekend" in plain(_text(exe.main))
    eng = _app(monkeypatch, runs, "engineering")
    table = next(d for d in eng.dataframe if "What happened" in list(d.value.columns))
    assert "Migration weekend" in set(table.value["What happened"])


def test_invalid_manual_events_do_not_break_the_page(monkeypatch, make_runs):
    runs = make_runs(events=[{"date": "nope"}, "junk", {"date": "2025-12-10", "label": "ok"}])
    at = _app(monkeypatch, runs, "engineering")
    assert not at.exception
    assert "skipped" in _text(at.main)


# --------------------------------------------------------------------- without daily
@pytest.mark.parametrize("view", ["executive", "engineering"])
def test_missing_daily_shows_a_clear_empty_state_never_fabricated_data(monkeypatch, make_runs, view):
    runs = make_runs(_drop_daily)
    at = _app(monkeypatch, runs, view)
    assert not at.exception
    assert EMPTY_STATE in _text(at.main)
    assert not [w for w in at.warning if "add up to" in w.value]
    if view == "executive":
        assert "charges stopped" not in _text(at.main)  # no invented events


@pytest.mark.parametrize("view", ["executive", "engineering"])
def test_legacy_run_without_any_new_fields_still_loads(monkeypatch, view):
    legacy = REPO / "fixtures"
    # The repo's top-level fixtures hold one legacy run (inventory/spend/advisor, no daily).
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp) / "runs"
        shutil.copytree(legacy, runs / "20250101-0000")
        at = _app(monkeypatch, runs, view)
        assert not at.exception
        assert EMPTY_STATE in _text(at.main)
