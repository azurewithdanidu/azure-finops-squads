"""Tests for Discovery's output contract: the daily spend series and the Discovery validator.

Offline-verified only: these use fixtures shaped like real Cost Management output; nothing here
has been exercised against a real Azure subscription.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import spend_daily as sd  # noqa: E402
import validate_discovery as vd  # noqa: E402

FIXTURES = REPO / "tests" / "fixtures"
COMPLETE = FIXTURES / "discovery" / "complete"
PERSONA_RUN = FIXTURES / "persona_runs" / "20260101-0000"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def spend():
    return copy.deepcopy(_load(COMPLETE / "spend.json"))


# ------------------------------------------------------------------------------- spend
def test_complete_fixture_run_is_valid_with_no_warnings():
    report = vd.validate_run(COMPLETE)
    assert all(errs == [] and warns == [] for errs, warns in report.values()), report


def test_legacy_spend_files_stay_valid():
    # The oldest fixture shape (monthly rows, no status) and a real-shaped aggregate file.
    legacy = _load(REPO / "fixtures" / "spend.json")
    errors, warnings = vd.validate_spend(legacy)
    assert errors == []
    assert any("daily spend series not captured" in w for w in warnings)

    aggregate_only = {
        "status": "available", "currency": "USD", "from": "2026-07-16", "to": "2026-10-14",
        "granularity": "None", "groupBy": "ServiceName", "totalLastMonth": 10.0,
        "byService": [{"service": "A", "cost": 10.0, "note": "n"}],
        "byResourceGroupTop10": [{"resourceGroup": "rg", "cost": 10.0}],
    }
    errors, warnings = vd.validate_spend(aggregate_only)
    assert errors == [] and len(warnings) == 1


def test_unavailable_spend_needs_a_reason_and_has_no_enrichment_warnings():
    assert vd.validate_spend({"status": "unavailable", "reason": "403 Forbidden"}) == ([], [])
    errors, _ = vd.validate_spend({"status": "unavailable"})
    assert any("reason" in e for e in errors)


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda s: s["daily"].pop("series"), "series"),
        (lambda s: s["daily"].update(series="nope"), "series"),
        (lambda s: s["daily"]["series"][0].update(date="01/01/2026"), "date"),
        (lambda s: s["daily"]["series"][0].update(cost="12"), "cost"),
        (lambda s: s["daily"]["series"].append(dict(s["daily"]["series"][0])), "duplicate"),
        (lambda s: s["daily"]["dailyTotal"].append(dict(s["daily"]["dailyTotal"][0])), "duplicate"),
        (lambda s: s["daily"]["series"][0].update(date="2025-01-01"), "outside"),
        (lambda s: s["daily"].update(provisionalFrom="2030-01-01"), "provisionalFrom"),
        (lambda s: s["daily"].update(currency="AUD"), "currency"),
        (lambda s: s["daily"]["dailyTotal"][3].update(cost=999.0), "add up"),
        (lambda s: s["daily"].update(truncated="yes"), "truncated"),
        (lambda s: s["daily"].update(**{"from": "2026-02-01"}), "before"),
    ],
)
def test_malformed_daily_blocks_are_errors(spend, mutate, expected):
    mutate(spend)
    errors, _ = vd.validate_spend(spend)
    assert errors, "expected an error"
    assert any(expected in e for e in errors), errors


def test_more_than_ten_named_services_is_an_error(spend):
    day = spend["daily"]["series"][0]["date"]
    spend["daily"]["series"] = [{"date": day, "service": f"svc-{i}", "cost": 1.0} for i in range(11)]
    spend["daily"]["dailyTotal"] = [
        {"date": r["date"], "cost": 11.0 if r["date"] == day else 0.0}
        for r in spend["daily"]["dailyTotal"]
    ]
    errors, _ = vd.validate_spend(spend)
    assert any("11 named services" in e for e in errors)


def test_other_row_does_not_count_towards_the_ten_service_limit(spend):
    day = spend["daily"]["series"][0]["date"]
    rows = [{"date": day, "service": f"svc-{i}", "cost": 1.0} for i in range(10)]
    rows.append({"date": day, "service": "Other", "cost": 2.0})
    spend["daily"]["series"] = rows
    spend["daily"]["dailyTotal"] = [
        {"date": r["date"], "cost": 12.0 if r["date"] == day else 0.0}
        for r in spend["daily"]["dailyTotal"]
    ]
    errors, _ = vd.validate_spend(spend)
    assert not any("named services" in e for e in errors)


def test_reconciliation_mismatch_and_truncation_are_warnings(spend):
    spend["totalLastMonth"] = spend["totalLastMonth"] * 1.05
    spend["daily"]["truncated"] = True
    errors, warnings = vd.validate_spend(spend)
    assert errors == []
    assert any("differs from the period total" in w for w in warnings)
    assert any("truncated" in w for w in warnings)


def test_reconcile_function_cases(spend):
    ok = sd.reconcile(spend)
    assert ok["status"] == "ok" and ok["deltaPct"] == 0.0
    near = {**spend, "totalLastMonth": spend["totalLastMonth"] * 1.005}
    assert sd.reconcile(near)["status"] == "ok"  # inside the 1% tolerance
    far = {**spend, "totalLastMonth": spend["totalLastMonth"] * 1.05}
    assert sd.reconcile(far)["status"] == "mismatch"
    assert sd.reconcile({**spend, "daily": None})["status"] == "skipped"
    assert sd.reconcile({k: v for k, v in spend.items() if k not in ("totalLastMonth", "byService")})[
        "status"
    ] == "skipped"
    other_window = {**spend, "to": "2026-01-15"}
    assert sd.reconcile(other_window)["status"] == "skipped"


def test_reconcile_never_compares_across_currencies(spend):
    spend["daily"]["currency"] = "AUD"
    result = sd.reconcile(spend)
    assert result["status"] == "skipped" and "currencies differ" in result["reason"]
    assert result["deltaPct"] is None


def test_daily_helpers_zero_fill_and_order(spend):
    daily = sd.get_daily(spend)
    assert len(sd.all_dates(daily)) == 31
    assert sd.service_order(daily) == ["Virtual Machines", "Storage"]
    assert str(sd.provisional_from(daily)) == "2026-01-29"
    assert str(sd.settled_through(daily)) == "2026-01-28"
    by = sd.series_by_service(daily)
    assert all(len(days) == 31 for days in by.values())
    daily_no_prov = {k: v for k, v in daily.items() if k != "provisionalFrom"}
    assert str(sd.provisional_from(daily_no_prov)) == "2026-01-29"  # defaults to the last 3 days
    assert sd.get_daily({}) is None and sd.get_daily({"daily": {"from": "x"}}) is None


def test_other_sorts_last():
    daily = {
        "from": "2026-01-01", "to": "2026-01-02",
        "series": [
            {"date": "2026-01-01", "service": "Other", "cost": 100.0},
            {"date": "2026-01-01", "service": "A", "cost": 1.0},
        ],
        "dailyTotal": [],
    }
    assert sd.service_order(daily) == ["A", "Other"]


# --------------------------------------------------------------------------- inventory
def test_inventory_missing_enrichments_warn_unless_skipped_with_reason():
    base = {"capturedAt": "x", "tagCoverage": {"total": 10, "missingOwner": 4}}
    errors, warnings = vd.validate_inventory(base)
    assert errors == []
    assert any("fullyTaggedCount" in w for w in warnings)
    assert any("resourceGroupTags" in w for w in warnings)

    skipped = {
        **base,
        "enrichmentSkipped": [
            {"field": "fullyTaggedCount", "reason": "Resource Graph query timed out"},
            {"field": "resourceGroupTags", "reason": "no permission to read resource groups"},
        ],
    }
    assert vd.validate_inventory(skipped) == ([], [])


def test_inventory_with_a_resources_array_does_not_need_fully_tagged_count():
    doc = {"resources": [{"id": "/subscriptions/x/a", "tags": {}}], "resourceGroupTags": {"rg": {}}}
    assert vd.validate_inventory(doc) == ([], [])


@pytest.mark.parametrize(
    "doc, expected",
    [
        ([], "JSON object"),
        ({"resources": {}}, "resources"),
        ({"resources": [{"name": "no id"}]}, "without an 'id'"),
        ({"tagCoverage": []}, "tagCoverage"),
        ({"tagCoverage": {"total": 0}}, "total"),
        ({"tagCoverage": {"total": 10, "fullyTaggedCount": 11}}, "fullyTaggedCount"),
        ({"tagCoverage": {"total": 10, "missingOwner": -1}}, "missingOwner"),
        ({"resourceGroupTags": {"rg": "oops"}}, "resourceGroupTags"),
        ({"enrichmentSkipped": "no"}, "enrichmentSkipped"),
        ({"enrichmentSkipped": [{"field": "fullyTaggedCount"}]}, "reason"),
        ({"enrichmentSkipped": [{"field": "fullyTaggedCount", "reason": "  "}]}, "reason"),
    ],
)
def test_malformed_inventory_is_an_error(doc, expected):
    errors, _ = vd.validate_inventory(doc)
    assert any(expected in e for e in errors), errors


def test_skipped_but_present_and_unknown_skip_fields_warn():
    doc = {
        "tagCoverage": {"total": 4, "fullyTaggedCount": 2},
        "resourceGroupTags": {"rg": {}},
        "enrichmentSkipped": [
            {"field": "fullyTaggedCount", "reason": "r"},
            {"field": "somethingElse", "reason": "r"},
        ],
    }
    errors, warnings = vd.validate_inventory(doc)
    assert errors == []
    assert any("skipped but is present" in w for w in warnings)
    assert any("unknown field" in w for w in warnings)


# ----------------------------------------------------------------------------- advisor
def test_advisor_shapes():
    assert vd.validate_advisor({"capturedAt": "x", "recommendations": []}) == ([], [])
    assert vd.validate_advisor({"capturedAt": "x", "summary": [{"recommendation": "r"}]}) == ([], [])
    assert vd.validate_advisor({"recommendations": []})[1] == ["capturedAt missing"]
    for bad in ([], {}, {"recommendations": ["str"]}, {"summary": 3}, {"recommendations": [], "totalCostRecommendations": -1}):
        assert vd.validate_advisor(bad)[0], bad


# --------------------------------------------------------------------------------- run
def test_validate_run_reports_missing_and_invalid_files(tmp_path):
    (tmp_path / "spend.json").write_text("{not json", encoding="utf-8")
    report = vd.validate_run(tmp_path)
    assert "missing" in report["inventory.json"][0][0]
    assert "invalid JSON" in report["spend.json"][0][0]


def test_cli_exit_codes_and_strict(tmp_path, capsys):
    assert vd.main(["validate_discovery.py", str(COMPLETE)]) == 0
    assert vd.main(["validate_discovery.py", str(tmp_path)]) == 1  # nothing to validate
    run = tmp_path / "r1"
    run.mkdir()
    (run / "inventory.json").write_text("{}", encoding="utf-8")
    (run / "spend.json").write_text(json.dumps({"status": "available"}), encoding="utf-8")
    (run / "advisor.json").write_text(
        json.dumps({"capturedAt": "x", "recommendations": []}), encoding="utf-8"
    )
    assert vd.main(["validate_discovery.py", str(run)]) == 0  # warnings only
    assert vd.main(["validate_discovery.py", str(run), "--strict"]) == 1
    assert vd.main(["validate_discovery.py"]) == 2
    capsys.readouterr()


def test_real_run_shapes_load_without_errors():
    runs = REPO / ".finops" / "runs"
    if not runs.is_dir():
        pytest.skip("no local runs (artifacts are git-ignored)")
    for run in runs.iterdir():
        for name, (errs, _) in vd.validate_run(run).items():
            assert errs == [], f"{run.name}/{name}: {errs}"


def test_skipped_daily_with_a_reason_is_accepted_without_a_warning(tmp_path):
    run = tmp_path / "r"
    run.mkdir()
    (run / "spend.json").write_text(json.dumps({"status": "available"}), encoding="utf-8")
    (run / "advisor.json").write_text(
        json.dumps({"capturedAt": "x", "recommendations": []}), encoding="utf-8"
    )
    inventory = {
        "tagCoverage": {"total": 2, "fullyTaggedCount": 1}, "resourceGroupTags": {},
        "enrichmentSkipped": [{"field": "daily", "reason": "Daily query returned HTTP 429 twice"}],
    }
    (run / "inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
    assert vd.validate_run(run)["spend.json"] == ([], [])
    inventory["enrichmentSkipped"][0]["reason"] = ""  # no reason -> not accepted
    (run / "inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
    assert vd.validate_run(run)["spend.json"][1], "an unexplained skip must still warn"
