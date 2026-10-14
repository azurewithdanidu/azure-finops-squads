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


def test_pick_schema_routing():
    assert validate.pick_schema(Path("x/findings/waste.json")) == validate.FINDING_SCHEMA
    assert validate.pick_schema(Path("x/verification/waste-0001.json")) == validate.VERIFICATION_SCHEMA
    assert validate.pick_schema(Path("x/inventory.json")) is None
