"""Tests for finops_store (local backend; blob backend shares the same RunStore logic)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from finops_store import LocalBackend, RunStore, StoreError, ValidationError, list_runs, list_subscriptions  # noqa: E402
from finops_store.upload import upload_runs  # noqa: E402

SUB = "11111111-2222-3333-4444-555555555555"
RUN = "20261019-2200"
FIXTURES = REPO / "fixtures"


@pytest.fixture
def store(tmp_path):
    return RunStore(LocalBackend(tmp_path), SUB, RUN)


def test_roundtrip_and_layout(store, tmp_path):
    key = store.write_json("spend.json", {"total": 1})
    assert key == f"{SUB}/runs/{RUN}/spend.json"
    assert (tmp_path / key).is_file()
    assert store.read_json("spend.json") == {"total": 1}
    assert store.exists("spend.json") and not store.exists("nope.json")
    store.write_text("reports/executive-summary.md", "# hi")
    assert store.read_text("reports/executive-summary.md") == "# hi"
    assert store.list() == ["reports/executive-summary.md", "spend.json"]


def test_valid_fixtures_accepted(store):
    findings = json.loads((FIXTURES / "findings" / "waste.json").read_text(encoding="utf-8"))
    store.write_json("findings/waste.json", findings)
    verification = json.loads((FIXTURES / "verification" / "waste-0001.json").read_text(encoding="utf-8"))
    store.write_json("verification/waste-0001.json", verification)


def test_invalid_finding_rejected_and_not_written(store):
    with pytest.raises(ValidationError):
        store.write_json("findings/waste.json", [{"id": "bad"}])
    assert not store.exists("findings/waste.json")


@pytest.mark.parametrize("rel", ["../x.json", "/abs.json", "a/../../b.json", "a\\b.json", "", "C:/x.json"])
def test_path_traversal_rejected(store, rel):
    with pytest.raises(StoreError):
        store.write_text(rel, "x")


@pytest.mark.parametrize("sub,run", [("not-a-guid", RUN), (SUB, "2026-10-19"), (SUB, "../x")])
def test_bad_ids_rejected(tmp_path, sub, run):
    with pytest.raises(StoreError):
        RunStore(LocalBackend(tmp_path), sub, run)


def test_listing_subscriptions_and_runs(tmp_path):
    backend = LocalBackend(tmp_path)
    for run in ("20261001-0900", "20261019-2200"):
        RunStore(backend, SUB, run).write_json("spend.json", {})
    assert list_subscriptions(backend) == [SUB]
    assert list_runs(backend, SUB) == ["20261019-2200", "20261001-0900"]


def test_upload_runs_validates(tmp_path):
    src = tmp_path / "runs"
    good = src / RUN / "findings"
    good.mkdir(parents=True)
    (good / "waste.json").write_text((FIXTURES / "findings" / "waste.json").read_text(encoding="utf-8"), encoding="utf-8")
    (src / RUN / "plan.md").write_text("plan", encoding="utf-8")
    bad = src / "20261020-0100" / "findings"
    bad.mkdir(parents=True)
    (bad / "waste.json").write_text("[{}]", encoding="utf-8")
    backend = LocalBackend(tmp_path / "store")
    uploaded, failures = upload_runs(src, SUB, backend)
    assert uploaded == 2
    assert len(failures) == 1 and "20261020-0100/findings/waste.json" in failures[0]
