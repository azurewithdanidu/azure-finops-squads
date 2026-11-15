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


def _empty_type_bucket() -> dict:
    return {
        "estimatedMonthly": 0.0,
        "realisedMonthly": 0.0,
        "findingCount": 0,
        "verifiedCount": 0,
    }


def _round_bucket(bucket: dict) -> dict:
    return {
        "estimatedMonthly": round(bucket["estimatedMonthly"], 2),
        "realisedMonthly": round(bucket["realisedMonthly"], 2),
        "findingCount": bucket["findingCount"],
        "verifiedCount": bucket["verifiedCount"],
    }


def build_ledger(run_folder: Path) -> dict:
    """Build a ledger, grouped by currency.

    A single run can legitimately mix currencies (e.g. a multi-subscription run, or a
    finding priced in a different billing currency than the report default). Totals are
    **never** summed across currencies — doing so silently produces a meaningless number.
    Instead every currency present gets its own totals/byType breakdown under `byCurrency`,
    and the top-level `currency`/`totals`/`byType` fields mirror whichever currency has the
    most findings (kept for backward compatibility with single-currency runs and existing
    consumers). `mixedCurrencies` is `true` whenever more than one currency is present, so
    any consumer can detect the case and must not assume the top-level totals are complete.
    """
    findings = {f["id"]: f for f in iter_findings(run_folder / "findings")}
    verifications = {v["findingId"]: v for v in iter_verifications(run_folder / "verification")}

    # by_currency[currency]["_totals"] holds the currency-level rollup;
    # by_currency[currency]["byType"][type] holds the per-type rollup within that currency.
    by_currency: dict[str, dict] = defaultdict(
        lambda: {"_totals": _empty_type_bucket(), "byType": defaultdict(_empty_type_bucket)}
    )

    for fid, finding in findings.items():
        ftype = finding.get("type", "unknown")
        saving = finding.get("estimatedMonthlySaving", {}) or {}
        amount = float(saving.get("amount", 0) or 0)
        fcurrency = saving.get("currency") or "AUD"

        bucket = by_currency[fcurrency]
        for target in (bucket["_totals"], bucket["byType"][ftype]):
            target["estimatedMonthly"] += amount
            target["findingCount"] += 1

        ver = verifications.get(fid)
        if ver and ver.get("result") in {"confirmed", "partial"}:
            realised = float(ver.get("realisedSaving", 0) or 0)
            for target in (bucket["_totals"], bucket["byType"][ftype]):
                target["realisedMonthly"] += realised
                target["verifiedCount"] += 1

    if not by_currency:
        return {
            "currency": "AUD",
            "mixedCurrencies": False,
            "totals": _round_bucket(_empty_type_bucket()),
            "byType": {},
            "byCurrency": {},
        }

    # The "primary" currency for the backward-compatible top-level fields is whichever
    # currency has the most findings (ties broken alphabetically for determinism) — never an
    # arbitrary "first one seen".
    primary_currency = max(
        by_currency,
        key=lambda c: (by_currency[c]["_totals"]["findingCount"], -ord(c[0])),
    )

    by_currency_out = {
        c: {
            "totals": _round_bucket(bucket["_totals"]),
            "byType": {t: _round_bucket(v) for t, v in sorted(bucket["byType"].items())},
        }
        for c, bucket in sorted(by_currency.items())
    }

    return {
        "currency": primary_currency,
        "mixedCurrencies": len(by_currency) > 1,
        "totals": by_currency_out[primary_currency]["totals"],
        "byType": by_currency_out[primary_currency]["byType"],
        "byCurrency": by_currency_out,
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
