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
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))  # dashboard modules import each other by name


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


validate = _load("validate_findings", "validate-findings.py")
ledger = _load("ledger", "ledger.py")
dashboard_helpers = _load("dashboard_helpers", "dashboard_helpers.py")
kpis = _load("kpis", "kpis.py")


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


# --------------------------------------------------------------------------------- kpis

def test_kpis_tagging_compliance_from_resources_list():
    # Exercises the "resources" method against the real fixtures/inventory.json -- none of the
    # 4 sample resources carry all 3 required tags (owner/environment/application), so compliance
    # is genuinely 0%, not a canned/synthetic result.
    result = kpis.build_kpis(REPO / "fixtures", runs_dir=None)
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
    ledger_result = ledger.build_ledger(REPO / "fixtures")
    result = kpis.build_kpis(REPO / "fixtures", runs_dir=None)
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


# ----------------------------------------------------------------- dashboard_helpers: KPIs

def test_load_kpis_missing_is_none(tmp_path: Path):
    assert dashboard_helpers.load_kpis(tmp_path) is None


def test_load_kpis_present(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "kpis.json").write_text(
        json.dumps({"kpis": {"estimatedSavingsOpportunity": {"value": 42.0}}}), encoding="utf-8"
    )
    loaded = dashboard_helpers.load_kpis(tmp_path)
    assert loaded is not None
    assert loaded["kpis"]["estimatedSavingsOpportunity"]["value"] == 42.0


def _write_kpis(run_dir: Path, metric: str, value):
    reports = run_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "kpis.json").write_text(
        json.dumps({"kpis": {metric: {"value": value}}}), encoding="utf-8"
    )


def test_kpi_trend_dataframe_rejects_unknown_metric(tmp_path: Path):
    try:
        dashboard_helpers.kpi_trend_dataframe([tmp_path], "notARealMetric")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_kpi_trend_dataframe_mixed_availability(tmp_path: Path):
    run_a = tmp_path / "20260101-0000"
    run_b = tmp_path / "20260102-0000"
    run_c = tmp_path / "20260103-0000"
    run_a.mkdir()
    run_b.mkdir()
    run_c.mkdir()
    # run_a: no kpis.json at all. run_b: kpis.json present but this metric is null.
    # run_c: kpis.json present with a real value.
    _write_kpis(run_b, "estimatedSavingsOpportunity", None)
    _write_kpis(run_c, "estimatedSavingsOpportunity", 149.81)

    df = dashboard_helpers.kpi_trend_dataframe(
        [run_a, run_b, run_c], "estimatedSavingsOpportunity"
    )
    assert list(df["runId"]) == ["20260101-0000", "20260102-0000", "20260103-0000"]
    assert list(df["available"]) == [False, False, True]
    assert df.iloc[2]["value"] == 149.81
    assert pd.isna(df.iloc[0]["value"])


# ------------------------------------------------- dashboard: presentation helpers and theme
def test_compact_number():
    f = dashboard_helpers.compact_number
    assert f(7.3) == "7.30"
    assert f(149.81) == "149.81"
    assert f(1234) == "1.2K"
    assert f(1000) == "1K"
    assert f(2_500_000) == "2.5M"
    assert f(-1500) == "-1.5K"
    assert f(None) == "—"


def test_md_escape_neutralises_markdown_and_html():
    out = dashboard_helpers.md_escape("[x](http://evil) <img src=x> **b** $a$")
    for ch in "[]()<>*$":
        assert out.count(ch) == out.count("\\" + ch), f"unescaped {ch!r} in {out!r}"
    assert dashboard_helpers.md_escape(None) == ""
    assert chr(10) not in dashboard_helpers.md_escape("a" + chr(10) + "b")


def test_safe_url_allows_only_http_s():
    assert dashboard_helpers.safe_url("https://github.com/o/r/pull/1") == "https://github.com/o/r/pull/1"
    assert dashboard_helpers.safe_url("javascript:alert(1)") is None
    assert dashboard_helpers.safe_url("data:text/html,x") is None
    assert dashboard_helpers.safe_url(None) is None


def test_confidence_label_and_short_id_and_is_approximate():
    assert dashboard_helpers.confidence_label("high").endswith("High")
    assert dashboard_helpers.confidence_label(None) == "—"
    assert dashboard_helpers.short_id("40668c14-2eac-4594-815f-e64abe2a25dd") == "40668c14…"
    assert dashboard_helpers.short_id("short") == "short"
    assert dashboard_helpers.is_approximate({"method": "tagCoverageApproximate"})
    assert not dashboard_helpers.is_approximate({"method": "exact"})
    assert not dashboard_helpers.is_approximate(None)


def test_money_format_rejects_unsafe_currency_codes():
    assert dashboard_helpers.money_format("AUD", False) == "AUD %.2f"
    assert dashboard_helpers.money_format("AUD", True) == "%.2f"
    assert dashboard_helpers.money_format("100%s", False) == "%.2f"
    assert dashboard_helpers.money_format(None, False) == "%.2f"


def test_findings_dataframe_prurl_only_keeps_safe_links():
    findings = [
        {"id": "a", "prUrl": "https://example.com/pr/1"},
        {"id": "b", "prUrl": "javascript:alert(1)"},
        {"id": "c"},
    ]
    df = dashboard_helpers.findings_dataframe(findings, {})
    assert df["prUrl"].tolist()[0] == "https://example.com/pr/1"
    assert df["prUrl"].isna().tolist()[1:] == [True, True]


def test_run_fingerprint_changes_when_a_file_changes(tmp_path):
    (tmp_path / "findings").mkdir()
    (tmp_path / "spend.json").write_text("{}", encoding="utf-8")
    before = dashboard_helpers.run_fingerprint(tmp_path)
    assert before == dashboard_helpers.run_fingerprint(tmp_path)
    (tmp_path / "findings" / "waste.json").write_text("[]", encoding="utf-8")
    after = dashboard_helpers.run_fingerprint(tmp_path)
    assert after != before and len(after) == 2


def test_theme_tokens_are_consistent():
    import dashboard_theme as T

    assert len(set(T.CATEGORICAL)) == len(T.CATEGORICAL)
    assert set(T.TIER_COLORS) == set(T.TIER_LABELS) == {"T0", "T1", "T2", "T3"}
    # tier labels carry the tier id, so tier is never conveyed by colour alone
    assert all(k in v for k, v in T.TIER_LABELS.items())
    T.register_altair_theme()
    T.register_altair_theme()  # idempotent


def test_chart_builders_return_valid_specs():
    import dashboard_charts as C

    bars = C.hbar_chart(
        pd.DataFrame({"s": ["a", "b"], "v": [1.0, 5.0]}), "s", "v", ["s", "v"]
    ).to_dict()
    assert bars["height"] >= 1
    vb = C.vbar_chart(pd.DataFrame({"k": ["x"], "n": [2]}), "k", "n", ["x"]).to_dict()
    assert vb["height"] == 300
    trend = C.trend_chart(
        pd.DataFrame({"runId": ["r1", "r2"], "value": [4.0, 5.0]}), ["r1", "r2"], "t", target=90
    ).to_dict()
    assert any(layer["mark"].get("strokeDash") for layer in trend["layer"] if isinstance(layer["mark"], dict))


# ------------------------------------------------- dashboard: buckets, headline, insights
import dashboard_insights as I  # noqa: E402  (scripts/ is on sys.path, see top of file)

PERSONA_RUNS = REPO / "tests" / "fixtures" / "persona_runs"
PERSONA_RUN = PERSONA_RUNS / "20260101-0000"


def _fixture_findings():
    return json.loads((PERSONA_RUN / "findings" / "waste.json").read_text(encoding="utf-8"))


def _f(tier="T1", iac="found", status="proposed", type_="orphaned-public-ip", amount=10.0, cur="AUD"):
    return {
        "id": "x", "type": type_, "tier": tier, "status": status,
        "iacMatch": {"status": iac}, "summary": "s", "confidence": "high", "effort": "low",
        "estimatedMonthlySaving": {"amount": amount, "currency": cur, "basis": "actual"},
    }


@pytest.mark.parametrize(
    "finding, bucket",
    [
        (_f("T1", "found"), "ready"),
        (_f("T0", "found"), "ready"),
        (_f("T2", "found"), "ready"),
        (_f("T1", "not-found"), "blocked_iac"),
        (_f("T2", "unmanaged"), "blocked_iac"),
        (_f("T3", "found"), "decision"),
        (_f(None, "found"), "decision"),
        (_f("T1", "found", status="pr-open"), "in_flight"),
        (_f("T3", "not-found", status="merged"), "in_flight"),
        (_f("T1", "found", status="verified"), "informational"),
        (_f("T0", "not-found", type_="anomaly"), "informational"),
    ],
)
def test_classify_finding(finding, bucket):
    assert dashboard_helpers.classify_finding(finding) == bucket


def test_type_labels_cover_the_schema_enum():
    schema = json.loads((REPO / "schemas" / "finding.schema.json").read_text(encoding="utf-8"))
    for t in schema["properties"]["type"]["enum"]:
        assert t in dashboard_helpers.TYPE_LABELS, f"no plain-English label for {t}"
    assert dashboard_helpers.type_label("brand-new-type") == "Brand new type"


def _headline(findings, spend=None, primary="AUD"):
    df = dashboard_helpers.findings_dataframe(findings, {})
    return I.build_headline(
        spend if spend is not None else {"status": "unavailable"},
        I.bucket_totals(df), I.realised_by_currency(df), primary,
    )


SPEND_OK = {
    "status": "available", "currency": "USD", "from": "2026-07-16", "to": "2026-10-14",
    "totalLastMonth": 6812.63,
}


def test_headline_single_currency():
    text = _headline(
        [_f("T1", "found", amount=5), _f("T2", "not-found", amount=12.42),
         _f("T3", "not-found", amount=137.39)], SPEND_OK,
    )
    assert "Spend was USD 6,812.63 over the 91 days to 14 Oct 2026 (about USD 2,277.12 a month)." in text
    assert "A$154.81 a month of estimated savings" in text
    assert "A$5.00 ready to action" in text
    assert "A$12.42 blocked on access to the infrastructure repo" in text
    assert "A$137.39 waiting on an owner decision" in text
    assert text.endswith("Realised so far: A$0.00.")


def test_headline_mixed_currency_never_adds_across_currencies():
    text = _headline([_f(amount=10, cur="AUD"), _f("T3", amount=7, cur="USD")], SPEND_OK)
    assert "never added together" in text
    assert "A$10.00 a month" in text and "USD 7.00 a month" in text
    assert "17" not in text  # no blended total
    assert text.endswith("Realised so far: A$0.00; USD 0.00.")


def test_headline_spend_unavailable_and_missing():
    assert _headline([_f()], {"status": "unavailable"}).startswith("Spend data is not available")
    assert _headline([_f()], {}).startswith("No spend breakdown was captured")
    no_dates = _headline([_f()], {"currency": "USD", "totalLastMonth": 100.0})
    assert "Spend was USD 100.00 in the period captured." in no_dates


def test_headline_zero_findings_and_zero_value_findings():
    empty = _headline([], SPEND_OK)
    assert "No findings yet, so no savings have been estimated." in empty
    assert empty.endswith("Realised so far: A$0.00.")
    zero = _headline([_f("T3", amount=0)], SPEND_OK)
    assert "none has an estimated saving yet" in zero


def test_headline_everything_blocked():
    text = _headline([_f("T1", "not-found", amount=8), _f("T2", "unmanaged", amount=2)], SPEND_OK)
    assert "A$10.00 a month of estimated savings: A$0.00 ready to action" in text
    assert "A$10.00 blocked on access to the infrastructure repo" in text
    assert "A$0.00 waiting on an owner decision" in text


def test_headline_bucket_amounts_equal_classify_finding_totals():
    findings = _fixture_findings()
    expected = {b: 0.0 for b in dashboard_helpers.BUCKETS}
    for f in findings:
        expected[dashboard_helpers.classify_finding(f)] += f["estimatedMonthlySaving"]["amount"]
    text = _headline(findings, SPEND_OK)
    assert f"{I.money_text('AUD', sum(expected.values()))} a month of estimated savings" in text
    assert f"{I.money_text('AUD', expected['ready'])} ready to action" in text
    assert f"{I.money_text('AUD', expected['blocked_iac'])} blocked on access" in text
    assert f"{I.money_text('AUD', expected['decision'])} waiting on an owner decision" in text
    # ... and the same amounts the ledger reports, so the two views and the ledger agree
    ledger_totals = ledger.build_ledger(PERSONA_RUN)["totals"]
    df = dashboard_helpers.findings_dataframe(findings, {})
    assert I.estimated_total(I.bucket_totals(df)["AUD"]) == ledger_totals["estimatedMonthly"]
    assert I.realised_by_currency(df)["AUD"] == ledger_totals["realisedMonthly"]


def test_insight_helpers():
    assert I.money_text("AUD", 1234.5) == "A$1,234.50"
    assert I.money_text("USD", 6812.63) == "USD 6,812.63"
    assert I.money_text("not a code", 1) == "? 1.00"
    assert I.monthly_run_rate(None, 91) is None and I.monthly_run_rate(100, 0) is None
    assert I.lead_sentence("First one. Second one.") == "First one."
    assert I.lead_sentence("x" * 500).endswith("…") and len(I.lead_sentence("x" * 500)) <= 240
    assert I.confidence_words("medium") == "Medium" and I.confidence_words(None) == "Not stated"
    half = {"baseline": {"value": 20}, "target": {"value": 0}, "current": {"value": 10}}
    assert I.goal_progress(half) == 0.5
    same = {"baseline": {"value": 5}, "target": {"value": 5}, "current": {"value": 5}}
    assert I.goal_progress(same) == 1.0
    assert I.goal_progress({"baseline": {"value": "n/a"}, "target": {"value": 1}}) is None
    over = {"baseline": {"value": 0}, "target": {"value": 1}, "current": {"value": 9}}
    assert I.goal_progress(over) == 1.0


def test_portal_url_only_for_arm_ids_and_is_encoded():
    rid = "/subscriptions/abc/resourceGroups/rg one/providers/x/y/z"
    expected = "https://portal.azure.com/#@/resource/subscriptions/abc/resourceGroups/rg%20one/providers/x/y/z"
    assert I.portal_url(rid) == expected
    assert I.portal_url("(subscription-scope)") is None
    assert I.portal_url(None) is None
    assert "<" not in (I.portal_url("/subscriptions/a/<script>") or "")


def test_blocker_and_next_step_rules():
    assert "iac-matching" in I.blocker_and_next_step(_f("T1", "not-found"))[1]
    assert "manual change request" in I.blocker_and_next_step(_f("T1", "unmanaged"))[1]
    blocker, step = I.blocker_and_next_step(_f("T3", "not-found"))
    assert "T3" in blocker and "will not act" in blocker and "owner" in step
    assert "draft" in I.blocker_and_next_step(_f("T2", "found"))[1]
    assert "verification" in I.blocker_and_next_step(_f(status="pr-open"))[1]
    assert "No action" in I.blocker_and_next_step(_f(type_="anomaly"))[1]


def test_tag_coverage_and_required_tags():
    inv = {"tagCoverage": {"total": 100, "missingOwner": 60, "missingEnvironment": 40}}
    rows = I.tag_coverage_rows(inv, ["owner", "environment", "application"])
    assert [r["tag"] for r in rows] == ["owner", "environment"]  # no data for application
    assert rows[0]["coverage"] == 40.0 and rows[1]["coverage"] == 60.0
    assert I.tag_coverage_rows(None, ["owner"]) == []
    assert I.required_tags({"requiredTags": ["owner"]}, {}) == ["owner"]
    assert I.required_tags(None, {"tagging": {"requiredTags": ["cost-centre"]}}) == ["cost-centre"]
    assert I.required_tags(None, {}) == I.DEFAULT_REQUIRED_TAGS


def test_artifact_checklist(tmp_path):
    assert not any(I.artifact_checklist(tmp_path).values())
    checklist = I.artifact_checklist(PERSONA_RUN)
    assert checklist["Spend"] and checklist["Findings"] and checklist["KPIs"]
    assert not checklist["Advisor"] and not checklist["Verification"]


def test_reliability_notes_plain_language():
    kpis_doc = json.loads((PERSONA_RUN / "reports" / "kpis.json").read_text(encoding="utf-8"))
    spend = json.loads((PERSONA_RUN / "spend.json").read_text(encoding="utf-8"))
    notes = " ".join(
        I.reliability_notes(
            spend, kpis_doc, {"timeWindow": {"start": "2025-10-01"}}, "AUD", True,
            {"allocationCoverage": "Allocation coverage"},
        )
    )
    assert "approximate" in notes
    assert "shortened" in notes
    assert "never converted or combined" in notes
    assert "more than one currency" in notes
    assert "Allocation coverage" in notes  # an unavailable KPI is named
    assert I.reliability_notes({}, None, {}, "AUD", False, {})[-1].startswith("No KPI set")


# ----------------------------------------------------- dashboard: AppTest smoke tests (personas)
def _dashboard_app(monkeypatch, runs_dir):
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("FINOPS_RUNS_DIR", str(runs_dir))
    return AppTest.from_file(str(SCRIPTS / "dashboard.py"), default_timeout=60)


def _all_text(node) -> str:
    """Every label/value rendered anywhere in an AppTest element tree."""
    parts = []
    for attr in ("value", "label", "body", "help"):
        v = getattr(node, attr, None)
        if isinstance(v, str):
            parts.append(v)
    for child in getattr(node, "children", {}).values():
        parts.append(_all_text(child))
    return "\n".join(parts)


def test_dashboard_renders_with_no_runs(monkeypatch, tmp_path):
    at = _dashboard_app(monkeypatch, tmp_path / "runs").run()
    assert not at.exception
    assert any("No runs found" in m.value for m in at.markdown)


def test_executive_view_has_no_tables_or_engineering_jargon(monkeypatch):
    at = _dashboard_app(monkeypatch, PERSONA_RUNS)
    at.query_params["view"] = "executive"
    at.run()
    assert not at.exception
    assert at.session_state["persona"] == "Executive"
    assert len(at.dataframe) == 0
    text = _all_text(at.main)
    assert not re.search(r"\bT[0-3]\b", text), "tier code leaked into the Executive view"
    for banned in ("iacMatch", "waste-0001", "anomaly-0001", "/subscriptions/", "Raw JSON"):
        assert banned not in text
    assert "ready to action" in text and "Decisions needed" in text
    assert "How reliable are these numbers?" in text
    assert any(m.label == "Estimated monthly opportunity" for m in at.metric)
    assert len(at.tabs) == 0


def test_engineering_view_has_queue_table_and_four_tabs(monkeypatch):
    at = _dashboard_app(monkeypatch, PERSONA_RUNS)
    at.query_params["view"] = "engineering"
    at.run()
    assert not at.exception
    assert len(at.tabs) == 4
    assert at.tabs[0].label.endswith("Work queue")
    assert len(at.dataframe) >= 1


def test_default_view_is_engineering_and_persona_switch_works(monkeypatch):
    at = _dashboard_app(monkeypatch, PERSONA_RUNS).run()
    assert not at.exception and at.session_state["persona"] == "Engineering"
    at.session_state["persona"] = "Executive"
    at.run()
    assert not at.exception and len(at.tabs) == 0


def test_invalid_query_params_fall_back_to_defaults(monkeypatch):
    at = _dashboard_app(monkeypatch, PERSONA_RUNS)
    at.query_params["view"] = "<script>"
    at.query_params["run"] = "no-such-run"
    at.run()
    assert not at.exception
    assert at.session_state["persona"] == "Engineering"
    assert at.session_state["run_name"] == "20260101-0000"


def test_both_views_show_the_same_headline_numbers(monkeypatch):
    texts = {}
    for view in ("executive", "engineering"):
        at = _dashboard_app(monkeypatch, PERSONA_RUNS)
        at.query_params["view"] = view
        at.run()
        assert not at.exception
        texts[view] = _all_text(at.main)
    totals = ledger.build_ledger(PERSONA_RUN)["totals"]
    assert I.money_text("AUD", totals["estimatedMonthly"]) in texts["executive"]
    assert f"{totals['estimatedMonthly']:,.2f}" in texts["engineering"]
