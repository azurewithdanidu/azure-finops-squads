"""Tests for the finops-squad helper scripts.

Run with: pytest tests/

Covers:
- fixtures validate against the schemas (positive gate)
- a deliberately malformed finding fails validation (negative gate)
- the ledger separates estimated from realised savings correctly
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


validate = _load("validate_findings", "validate-findings.py")
ledger = _load("ledger", "ledger.py")
dashboard_helpers = _load("dashboard_helpers", "dashboard_helpers.py")


def test_fixtures_are_valid():
    waste = REPO / "fixtures" / "findings" / "waste.json"
    errors = validate.validate_file(waste, validate.FINDING_SCHEMA)
    assert errors == [], f"expected valid fixtures, got: {errors}"

    ver = REPO / "fixtures" / "verification" / "waste-0001.json"
    errors = validate.validate_file(ver, validate.VERIFICATION_SCHEMA)
    assert errors == [], f"expected valid verification, got: {errors}"


def test_invalid_finding_is_rejected():
    bad = REPO / "tests" / "invalid" / "findings" / "bad.json"
    errors = validate.validate_file(bad, validate.FINDING_SCHEMA)
    assert errors, "malformed finding should produce validation errors"
    blob = " ".join(errors)
    # missing required 'tier', empty 'evidence', and blank price 'basis'
    assert "tier" in blob
    assert "evidence" in blob
    assert "basis" in blob


def test_ledger_separates_estimated_and_realised():
    result = ledger.build_ledger(REPO / "fixtures")
    totals = result["totals"]
    # 24.58 + 4.86 + 165.40 + 0 = 194.84 estimated
    assert totals["estimatedMonthly"] == 194.84
    # only waste-0001 is verified/confirmed => 24.58 realised
    assert totals["realisedMonthly"] == 24.58
    assert totals["findingCount"] == 4
    assert totals["verifiedCount"] == 1
    assert result["byType"]["orphaned-disk"]["realisedMonthly"] == 24.58
    assert result["byType"]["idle-vm"]["realisedMonthly"] == 0.0
    assert result["mixedCurrencies"] is False


def test_ledger_never_sums_mixed_currencies():
    result = ledger.build_ledger(REPO / "tests" / "fixtures" / "mixed_currency")
    assert result["mixedCurrencies"] is True
    # AUD has 2 findings (waste-0001, waste-0002), USD has 1 (waste-0003) -> AUD is primary
    assert result["currency"] == "AUD"
    assert result["totals"]["findingCount"] == 2
    assert result["totals"]["estimatedMonthly"] == round(24.58 + 4.86, 2)
    # The USD finding must never be blended into the AUD total.
    assert result["totals"]["estimatedMonthly"] != round(24.58 + 4.86 + 92.00, 2)
    by_currency = result["byCurrency"]
    assert set(by_currency) == {"AUD", "USD"}
    assert by_currency["AUD"]["totals"]["estimatedMonthly"] == round(24.58 + 4.86, 2)
    assert by_currency["USD"]["totals"]["estimatedMonthly"] == 92.00
    assert by_currency["USD"]["totals"]["findingCount"] == 1


def test_pick_schema_routing():
    assert validate.pick_schema(Path("x/findings/waste.json")) == validate.FINDING_SCHEMA
    assert validate.pick_schema(Path("x/verification/waste-0001.json")) == validate.VERIFICATION_SCHEMA
    assert validate.pick_schema(Path("x/inventory.json")) is None


# --------------------------------------------------------------------- dashboard_helpers

def test_load_findings_empty_run(tmp_path: Path):
    # No findings/ directory at all -> empty list, not an error.
    assert dashboard_helpers.load_findings(tmp_path) == []


def test_load_findings_incomplete_run(tmp_path: Path):
    # A findings/ directory that exists but is empty, plus a malformed sibling file.
    fdir = tmp_path / "findings"
    fdir.mkdir()
    (fdir / "waste.json").write_text("{not valid json", encoding="utf-8")
    assert dashboard_helpers.load_findings(tmp_path) == []


def test_load_verifications_empty_run(tmp_path: Path):
    assert dashboard_helpers.load_verifications(tmp_path) == {}


def test_load_iteration_missing_is_none(tmp_path: Path):
    # No iteration.json -> None, and the dashboard must treat this as "no brief", not an error.
    assert dashboard_helpers.load_iteration(tmp_path) is None


def test_load_iteration_present(tmp_path: Path):
    (tmp_path / "iteration.json").write_text(
        json.dumps({"iterationId": "test-iter-01", "goals": []}), encoding="utf-8"
    )
    iteration = dashboard_helpers.load_iteration(tmp_path)
    assert iteration is not None
    assert iteration["iterationId"] == "test-iter-01"


def test_compare_runs_resolved_new_recurring():
    common = {"type": "orphaned-disk", "resourceId": "/rid/common"}
    resolved_only = {"type": "orphaned-nic", "resourceId": "/rid/resolved"}
    new_only = {"type": "tagging-gap", "resourceId": "/rid/new"}

    diff = dashboard_helpers.compare_runs([common, resolved_only], [common, new_only])

    assert diff["resolved"] == [resolved_only]
    assert diff["new"] == [new_only]
    assert diff["recurring"] == [common]


def test_compare_runs_matches_by_type_and_resource_not_id():
    # Same underlying resource, different per-run `id` numbering -> still "recurring", not "new"
    # and "resolved" at the same time.
    a = {"id": "waste-0001", "type": "orphaned-public-ip", "resourceId": "/rid/pip"}
    b = {"id": "waste-0007", "type": "orphaned-public-ip", "resourceId": "/rid/pip"}
    diff = dashboard_helpers.compare_runs([a], [b])
    assert diff["recurring"] == [b]
    assert diff["resolved"] == []
    assert diff["new"] == []


def test_findings_dataframe_empty():
    df = dashboard_helpers.findings_dataframe([], {})
    assert df.empty


def test_findings_dataframe_preserves_per_row_currency():
    # findings_dataframe must never blend currencies -- it carries each finding's own currency
    # on its own row; only a naive .sum() across rows (which the dashboard must guard against
    # via ledger["mixedCurrencies"]) would blend them.
    findings = [
        {"id": "a", "type": "orphaned-disk", "estimatedMonthlySaving": {"amount": 10, "currency": "AUD"}},
        {"id": "b", "type": "idle-vm", "estimatedMonthlySaving": {"amount": 20, "currency": "USD"}},
    ]
    df = dashboard_helpers.findings_dataframe(findings, {})
    assert list(df["currency"]) == ["AUD", "USD"]
    assert list(df["estimatedMonthly"]) == [10.0, 20.0]


def test_load_json_malformed_returns_none(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    assert dashboard_helpers.load_json(bad) is None
