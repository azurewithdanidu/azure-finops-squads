#!/usr/bin/env python3
"""Build a savings ledger from findings and verification artifacts.

Usage:
    python scripts/ledger.py <run-folder> [--out <path>]

Scans <run-folder>/findings/*.json and <run-folder>/verification/*.json and
produces a savings-ledger.json that separates ESTIMATED savings (from findings)
from REALISED savings (from confirmed/partial verifications), grouped by finding
type. Estimates are never counted as realised.

If --out is omitted the ledger is written to
<run-folder>/reports/savings-ledger.json and also printed to stdout.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def iter_findings(findings_dir: Path):
    if not findings_dir.is_dir():
        return
    for path in sorted(findings_dir.glob("*.json")):
        doc = load_json(path)
        items = doc if isinstance(doc, list) else doc.get("findings", [doc])
        for item in items:
            if isinstance(item, dict) and "id" in item:
                yield item


def iter_verifications(verification_dir: Path):
    if not verification_dir.is_dir():
        return
    for path in sorted(verification_dir.glob("*.json")):
        doc = load_json(path)
        if isinstance(doc, dict) and "findingId" in doc:
            yield doc


def build_ledger(run_folder: Path) -> dict:
    findings = {f["id"]: f for f in iter_findings(run_folder / "findings")}
    verifications = {v["findingId"]: v for v in iter_verifications(run_folder / "verification")}

    by_type: dict[str, dict] = defaultdict(
        lambda: {
            "estimatedMonthly": 0.0,
            "realisedMonthly": 0.0,
            "findingCount": 0,
            "verifiedCount": 0,
        }
    )
    currency = None
    estimated_total = 0.0
    realised_total = 0.0

    for fid, finding in findings.items():
        ftype = finding.get("type", "unknown")
        saving = finding.get("estimatedMonthlySaving", {})
        amount = float(saving.get("amount", 0) or 0)
        currency = currency or saving.get("currency")
        by_type[ftype]["estimatedMonthly"] += amount
        by_type[ftype]["findingCount"] += 1
        estimated_total += amount

        ver = verifications.get(fid)
        if ver and ver.get("result") in {"confirmed", "partial"}:
            realised = float(ver.get("realisedSaving", 0) or 0)
            by_type[ftype]["realisedMonthly"] += realised
            by_type[ftype]["verifiedCount"] += 1
            realised_total += realised

    return {
        "currency": currency or "AUD",
        "totals": {
            "estimatedMonthly": round(estimated_total, 2),
            "realisedMonthly": round(realised_total, 2),
            "findingCount": len(findings),
            "verifiedCount": sum(1 for v in verifications.values()
                                 if v.get("result") in {"confirmed", "partial"}),
        },
        "byType": {
            t: {
                "estimatedMonthly": round(v["estimatedMonthly"], 2),
                "realisedMonthly": round(v["realisedMonthly"], 2),
                "findingCount": v["findingCount"],
                "verifiedCount": v["verifiedCount"],
            }
            for t, v in sorted(by_type.items())
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_folder", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if not args.run_folder.is_dir():
        print(f"ERROR: run folder not found: {args.run_folder}")
        return 2

    ledger = build_ledger(args.run_folder)
    out = args.out or (args.run_folder / "reports" / "savings-ledger.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(ledger, fh, indent=2)
        fh.write("\n")
    print(json.dumps(ledger, indent=2))
    print(f"\nLedger written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
