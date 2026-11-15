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
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "plugins" / "finops-squad" / "skills" / "finops-squad" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


validate = _load("validate_findings", "validate-findings.py")
ledger = _load("ledger", "ledger.py")
kpis = _load("kpis", "kpis.py")


def test_fixtures_are_valid():
    waste = REPO / "plugins" / "finops-squad" / "evals" / "fixtures" / "legacy" / "findings" / "waste.json"
    errors = validate.validate_file(waste, validate.FINDING_SCHEMA)
    assert errors == [], f"expected valid fixtures, got: {errors}"

    ver = REPO / "plugins" / "finops-squad" / "evals" / "fixtures" / "legacy" / "verification" / "waste-0001.json"
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
    result = ledger.build_ledger(REPO / "plugins" / "finops-squad" / "evals" / "fixtures" / "legacy")
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


# --------------------------------------------------------------------------------- kpis

def test_kpis_tagging_compliance_from_resources_list():
    # Exercises the "resources" method against the real fixtures/inventory.json -- none of the
    # 4 sample resources carry all 3 required tags (owner/environment/application), so compliance
    # is genuinely 0%, not a canned/synthetic result.
    result = kpis.build_kpis(REPO / "plugins" / "finops-squad" / "evals" / "fixtures" / "legacy", runs_dir=None)
    tc = result["kpis"]["taggingCompliance"]
    assert tc["method"] == "resources"
    assert tc["value"] == 0.0
    assert tc["meetsTarget"] is False
    assert tc["target"] == 90


def test_kpis_tagging_compliance_unavailable_without_inventory(tmp_path: Path):
    result = kpis.build_kpis(tmp_path, runs_dir=None)
    tc = result["kpis"]["taggingCompliance"]
    assert tc["method"] == "unavailable"
    assert tc["value"] is None
    assert tc["meetsTarget"] is None


def test_kpis_tagging_compliance_exact_from_fully_tagged_count(tmp_path: Path):
    (tmp_path / "inventory.json").write_text(
        json.dumps({"tagCoverage": {"total": 100, "fullyTaggedCount": 92}}), encoding="utf-8"
    )
    result = kpis.build_kpis(tmp_path, runs_dir=None)
    tc = result["kpis"]["taggingCompliance"]
    assert tc["method"] == "tagCoverageFullyTagged"
    assert tc["value"] == 92.0
    assert tc["meetsTarget"] is True


def test_kpis_tagging_compliance_approximate_fallback(tmp_path: Path):
    # No fullyTaggedCount -- falls back to an upper-bound approximation from the worst single
    # per-tag missing count (the live-run shape captured by finops-discovery when a full
    # per-resource scan wasn't performed).
    (tmp_path / "inventory.json").write_text(
        json.dumps({"tagCoverage": {
            "total": 487, "missingOwner": 467, "missingEnvironment": 426, "missingApplication": 459,
        }}),
        encoding="utf-8",
    )
    result = kpis.build_kpis(tmp_path, runs_dir=None)
    tc = result["kpis"]["taggingCompliance"]
    assert tc["method"] == "tagCoverageApproximate"
    # worst missing = 467 -> (487-467)/487 = 4.1%
    assert tc["value"] == 4.1
    assert tc["meetsTarget"] is False
    assert "UPPER BOUND" in tc["note"]


def test_kpis_tag_synonym_handling_env_vs_environment():
    # fixtures/inventory.json uses "env", not "environment" -- the default required tag list
    # must still match it via the synonym table, not silently fail to recognise the tag.
    assert kpis._tag_has_all({"env": "dev", "owner": "x", "application": "y"}, kpis.DEFAULT_REQUIRED_TAGS)
    assert not kpis._tag_has_all({"env": "dev"}, kpis.DEFAULT_REQUIRED_TAGS)


def test_kpis_allocation_coverage_unavailable_without_spend_breakdown(tmp_path: Path):
    (tmp_path / "inventory.json").write_text(
        json.dumps({"resourceGroupTags": {"rg-a": {"owner": "x"}}}), encoding="utf-8"
    )
    result = kpis.build_kpis(tmp_path, runs_dir=None)
    ac = result["kpis"]["allocationCoverage"]
    assert ac["method"] == "unavailable"
    assert ac["value"] is None


def test_kpis_allocation_coverage_unavailable_without_resource_group_tags(tmp_path: Path):
    (tmp_path / "spend.json").write_text(
        json.dumps({"byResourceGroup": [{"resourceGroup": "rg-a", "cost": 100}]}), encoding="utf-8"
    )
    result = kpis.build_kpis(tmp_path, runs_dir=None)
    ac = result["kpis"]["allocationCoverage"]
    assert ac["method"] == "unavailable"
    assert ac["value"] is None


def test_kpis_allocation_coverage_computed(tmp_path: Path):
    (tmp_path / "spend.json").write_text(
        json.dumps({"byResourceGroup": [
            {"resourceGroup": "rg-tagged", "cost": 300},
            {"resourceGroup": "rg-untagged", "cost": 100},
        ]}),
        encoding="utf-8",
    )
    (tmp_path / "inventory.json").write_text(
        json.dumps({"resourceGroupTags": {
            "rg-tagged": {"owner": "platform", "environment": "prod", "application": "payments"},
            "rg-untagged": {},
        }}),
        encoding="utf-8",
    )
    result = kpis.build_kpis(tmp_path, runs_dir=None)
    ac = result["kpis"]["allocationCoverage"]
    assert ac["method"] == "resourceGroupJoin"
    # 300 / (300+100) = 75%
    assert ac["value"] == 75.0


def test_kpis_estimated_and_realised_savings_reuse_ledger(tmp_path: Path):
    # kpis.py must reuse ledger.build_ledger's own logic rather than re-deriving totals --
    # reusing the fixtures/ run folder proves the two scripts agree.
    ledger_result = ledger.build_ledger(REPO / "plugins" / "finops-squad" / "evals" / "fixtures" / "legacy")
    result = kpis.build_kpis(REPO / "plugins" / "finops-squad" / "evals" / "fixtures" / "legacy", runs_dir=None)
    est = result["kpis"]["estimatedSavingsOpportunity"]
    real = result["kpis"]["realisedSavingsRate"]
    assert est["value"] == ledger_result["totals"]["estimatedMonthly"]
    assert est["currency"] == ledger_result["currency"]
    expected_rate = round(
        100.0 * ledger_result["totals"]["realisedMonthly"] / ledger_result["totals"]["estimatedMonthly"], 1
    )
    assert real["value"] == expected_rate


def test_kpis_realised_savings_rate_zero_when_no_estimate(tmp_path: Path):
    result = kpis.build_kpis(tmp_path, runs_dir=None)
    assert result["kpis"]["realisedSavingsRate"]["value"] == 0.0


def _write_anomaly_finding(run_dir: Path, finding_id: str):
    fdir = run_dir / "findings"
    fdir.mkdir(parents=True, exist_ok=True)
    (fdir / "anomalies.json").write_text(
        json.dumps([{"id": finding_id, "type": "anomaly", "resourceId": "/rid/x"}]),
        encoding="utf-8",
    )


def test_kpis_anomaly_count_unavailable_without_earlier_run(tmp_path: Path):
    run_a = tmp_path / "20260101-0000"
    run_a.mkdir()
    _write_anomaly_finding(run_a, "anomaly-0001")
    result = kpis.build_kpis(run_a, runs_dir=tmp_path)
    ac = result["kpis"]["anomalyCount"]
    assert ac["trend"] == "unavailable"
    assert ac["value"] == 1
    assert ac["previousRunId"] is None


def test_kpis_anomaly_count_trend_up(tmp_path: Path):
    run_a = tmp_path / "20260101-0000"
    run_b = tmp_path / "20260102-0000"
    run_a.mkdir()
    run_b.mkdir()
    # run_a has 0 anomalies, run_b has 1 -> trend up
    _write_anomaly_finding(run_b, "anomaly-0001")
    result = kpis.build_kpis(run_b, runs_dir=tmp_path)
    ac = result["kpis"]["anomalyCount"]
    assert ac["previousRunId"] == "20260101-0000"
    assert ac["previousValue"] == 0
    assert ac["value"] == 1
    assert ac["delta"] == 1
    assert ac["trend"] == "up"


def test_kpis_anomaly_count_trend_flat(tmp_path: Path):
    run_a = tmp_path / "20260101-0000"
    run_b = tmp_path / "20260102-0000"
    run_a.mkdir()
    run_b.mkdir()
    _write_anomaly_finding(run_a, "anomaly-0001")
    _write_anomaly_finding(run_b, "anomaly-0001")
    result = kpis.build_kpis(run_b, runs_dir=tmp_path)
    ac = result["kpis"]["anomalyCount"]
    assert ac["delta"] == 0
    assert ac["trend"] == "flat"


def test_kpis_mixed_currency_run_notes_it_in_estimated_savings():
    result = kpis.build_kpis(REPO / "tests" / "fixtures" / "mixed_currency", runs_dir=None)
    assert result["mixedCurrencies"] is True
    assert "mixes currencies" in result["kpis"]["estimatedSavingsOpportunity"]["note"]
