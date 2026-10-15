"""Pure/IO helpers for the finops-squad dashboard, kept separate from scripts/dashboard.py so they
can be imported and unit-tested without triggering Streamlit's script-runner context.

Nothing in this module calls Streamlit, Azure, or mutates any artifact — it only reads
`.finops/runs/<id>/` files and shapes them into plain dicts / DataFrames.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

TIER_ORDER = ["T0", "T1", "T2", "T3"]
TIER_COLORS = {"T0": "#34a853", "T1": "#4285f4", "T2": "#f9ab00", "T3": "#ea4335"}
STATUS_ORDER = ["proposed", "approved", "pr-open", "merged", "verified", "rejected"]


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_runs(runs_dir: Path) -> list[Path]:
    if not runs_dir.is_dir():
        return []
    return sorted((p for p in runs_dir.iterdir() if p.is_dir()), reverse=True)


def load_findings(run: Path) -> list[dict]:
    findings: list[dict] = []
    fdir = run / "findings"
    if not fdir.is_dir():
        return findings
    for path in sorted(fdir.glob("*.json")):
        doc = load_json(path)
        if doc is None:
            continue
        items = doc if isinstance(doc, list) else doc.get("findings", [doc])
        for item in items:
            if isinstance(item, dict) and "id" in item:
                findings.append(item)
    return findings


def load_verifications(run: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    vdir = run / "verification"
    if not vdir.is_dir():
        return out
    for path in sorted(vdir.glob("*.json")):
        doc = load_json(path)
        if isinstance(doc, dict) and "findingId" in doc:
            out[doc["findingId"]] = doc
    return out


def load_iteration(run: Path) -> dict | None:
    """Load the structured iteration brief (iteration.json), if one was captured for this run.

    Returns None when the run has no iteration brief — iteration tracking is optional, and the
    dashboard must render exactly as before for any run that didn't use it.
    """
    return load_json(run / "iteration.json")


def compare_runs(findings_a: list[dict], findings_b: list[dict]) -> dict[str, list[dict]]:
    """Diff two runs' findings by (type, resourceId) — not by `id`, which is only stable within a
    single run's own numbering. Returns:
    - "resolved": present in `findings_a` (the earlier run) but not in `findings_b` (the later run)
    - "new": present in `findings_b` but not in `findings_a`
    - "recurring": present in both — i.e. still open since the earlier run
    Used to tell a repeat scan apart from real progress (see finops-reporting's retrospective).
    """

    def key(f: dict) -> tuple:
        return (f.get("type"), f.get("resourceId"))

    by_key_a = {key(f): f for f in findings_a}
    by_key_b = {key(f): f for f in findings_b}
    keys_a, keys_b = set(by_key_a), set(by_key_b)

    return {
        "resolved": [by_key_a[k] for k in sorted(keys_a - keys_b, key=str)],
        "new": [by_key_b[k] for k in sorted(keys_b - keys_a, key=str)],
        "recurring": [by_key_b[k] for k in sorted(keys_a & keys_b, key=str)],
    }


def findings_dataframe(findings: list[dict], verifs: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for f in findings:
        saving = f.get("estimatedMonthlySaving", {}) or {}
        iac = f.get("iacMatch", {}) or {}
        ver = verifs.get(f.get("id"))
        rows.append(
            {
                "id": f.get("id"),
                "type": f.get("type"),
                "tier": f.get("tier"),
                "estimatedMonthly": float(saving.get("amount", 0) or 0),
                "currency": saving.get("currency", "AUD"),
                "basis": saving.get("basis"),
                "confidence": f.get("confidence"),
                "effort": f.get("effort"),
                "iacMatch": iac.get("status"),
                "status": f.get("status"),
                "verifiedResult": (ver or {}).get("result"),
                "realisedMonthly": float((ver or {}).get("realisedSaving", 0) or 0)
                if ver and ver.get("result") in {"confirmed", "partial"}
                else 0.0,
                "resourceId": f.get("resourceId"),
                "summary": f.get("summary"),
            }
        )
    return pd.DataFrame(rows)
