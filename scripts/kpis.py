#!/usr/bin/env python3
"""Build a named FinOps KPI set from run artifacts.

Usage:
    python scripts/kpis.py <run-folder> [--out <path>] [--runs-dir <path>]

Computes a small, named KPI set per the FinOps Foundation Framework's KPIs & Benchmarking
capability (https://www.finops.org/framework/capabilities/kpis-benchmarking/), which calls for
"a curated, well-documented set of KPIs... regularly reviewed for relevance" rather than raw,
unnamed totals:

- taggingCompliance           -- % of resources carrying every required tag, compared against the
                                  Framework's own named target: ">90% Overall Tagging Compliance"
                                  (Reporting & Analytics capability).
- allocationCoverage          -- % of spend attributable to resource groups with full tag
                                  coverage (Reporting & Analytics' "allocated vs unallocated
                                  resources" output).
- estimatedSavingsOpportunity -- the savings ledger's primary-currency estimated total.
- realisedSavingsRate         -- realised / estimated, as a percentage, for the primary currency.
- anomalyCount                -- count of `type: "anomaly"` findings this run, trended against
                                  the nearest earlier run (Anomaly Management's maturity bar:
                                  persisting the baseline across runs, not just within one).

Every KPI is computed only from data actually present in the run folder. When the required
inputs are missing, the KPI reports `"method"/"trend": "unavailable"` and an honest `note`
explaining what's missing -- never a fabricated number (the same honesty rule applied to
spend.json's `"status": "unavailable"` elsewhere in this project).

If --out is omitted, the KPI set is written to <run-folder>/reports/kpis.json and printed
to stdout.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

# The tagging-policy-design skill's published taxonomy uses "env" as the canonical key; some
# tenants use "Environment" instead. Required-tag matching is synonym- and case-insensitive so
# a run never reports an artificially low compliance number purely due to a naming convention.
DEFAULT_REQUIRED_TAGS = ["owner", "environment", "application"]
TAG_SYNONYMS = {
    "environment": ["environment", "env"],
    "owner": ["owner"],
    "application": ["application", "app"],
    "costcenter": ["costcenter", "cost_center", "cost-center"],
}


def load_json(path: Path):
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _iter_findings(findings_dir: Path):
    if not findings_dir.is_dir():
        return
    for path in sorted(findings_dir.glob("*.json")):
        doc = load_json(path)
        if doc is None:
            continue
        items = doc if isinstance(doc, list) else doc.get("findings", [doc])
        for item in items:
            if isinstance(item, dict) and "id" in item:
                yield item


def _build_ledger(run_folder: Path) -> dict:
    """Load ledger.py by file path (not `import ledger`) so this works regardless of whether
    scripts/ happens to be on sys.path -- see tests/test_scripts.py for the same pattern."""
    spec = importlib.util.spec_from_file_location(
        "ledger", Path(__file__).resolve().parent / "ledger.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod.build_ledger(run_folder)


def _required_tags(run_folder: Path) -> list[str]:
    # .finops/runs/<id>/ -> .finops/config.json
    config = load_json(run_folder.resolve().parent.parent / "config.json") or {}
    tags = (config.get("tagging") or {}).get("requiredTags")
    if isinstance(tags, list) and tags:
        return [str(t).lower() for t in tags]
    return list(DEFAULT_REQUIRED_TAGS)


def _tag_has_all(tags: dict, required: list[str]) -> bool:
    lowered = {str(k).lower(): v for k, v in (tags or {}).items()}
    for req in required:
        synonyms = TAG_SYNONYMS.get(req.lower(), [req.lower()])
        if not any(bool(lowered.get(s)) for s in synonyms):
            return False
    return True


def compute_tagging_compliance(inventory: dict | None, required: list[str]) -> dict:
    if not inventory:
        return {
            "value": None, "unit": "percent", "target": 90, "meetsTarget": None,
            "method": "unavailable",
            "note": "inventory.json not found or unreadable for this run.",
        }

    resources = inventory.get("resources")
    if isinstance(resources, list) and resources:
        total = len(resources)
        fully = sum(1 for r in resources if _tag_has_all(r.get("tags") or {}, required))
        pct = round(100.0 * fully / total, 1)
        return {
            "value": pct, "unit": "percent", "target": 90,
            "meetsTarget": pct >= 90,
            "method": "resources",
            "note": f"Computed from {total} resource(s) in inventory.resources against required tags {required}.",
        }

    tag_coverage = inventory.get("tagCoverage")
    if isinstance(tag_coverage, dict) and tag_coverage.get("total"):
        total = tag_coverage["total"]
        fully_tagged = tag_coverage.get("fullyTaggedCount")
        if fully_tagged is not None:
            pct = round(100.0 * fully_tagged / total, 1)
            return {
                "value": pct, "unit": "percent", "target": 90,
                "meetsTarget": pct >= 90,
                "method": "tagCoverageFullyTagged",
                "note": f"Computed from inventory.tagCoverage.fullyTaggedCount ({fully_tagged}/{total}).",
            }
        # No combined fully-tagged count -- fall back to an upper-bound approximation from the
        # single worst per-tag missing count. True compliance (ALL required tags present) can
        # only be lower than this, since a resource missing any one tag is already non-compliant.
        missing_counts = [
            v for k, v in tag_coverage.items()
            if k.lower().startswith("missing") and isinstance(v, (int, float))
        ]
        if missing_counts:
            worst_missing = max(missing_counts)
            approx_pct = round(100.0 * (total - worst_missing) / total, 1)
            return {
                "value": approx_pct, "unit": "percent", "target": 90,
                "meetsTarget": approx_pct >= 90,
                "method": "tagCoverageApproximate",
                "note": (
                    "UPPER BOUND approximation from the single worst per-tag missing count (no "
                    "fullyTaggedCount available) -- true compliance is likely lower. Re-run "
                    "Discovery with the fully-tagged-resource-count query in resource-graph-kql's "
                    "reference catalog for an exact figure."
                ),
            }

    return {
        "value": None, "unit": "percent", "target": 90, "meetsTarget": None,
        "method": "unavailable",
        "note": "inventory.json has neither a resources[] array nor tagCoverage data.",
    }


def _spend_by_resource_group(spend: dict | None) -> dict[str, float]:
    if not spend:
        return {}
    rows = spend.get("byResourceGroup") or spend.get("byResourceGroupTop10") or []
    out: dict[str, float] = {}
    for row in rows:
        rg, cost = row.get("resourceGroup"), row.get("cost")
        if rg and isinstance(cost, (int, float)):
            out[rg] = cost
    return out


def compute_allocation_coverage(inventory: dict | None, spend: dict | None, required: list[str]) -> dict:
    rg_spend = _spend_by_resource_group(spend)
    rg_tags = (inventory or {}).get("resourceGroupTags")

    if not rg_spend:
        return {
            "value": None, "unit": "percent", "method": "unavailable",
            "note": "spend.json has no byResourceGroup/byResourceGroupTop10 breakdown for this run.",
        }
    if not isinstance(rg_tags, dict) or not rg_tags:
        return {
            "value": None, "unit": "percent", "method": "unavailable",
            "note": "inventory.json has no resourceGroupTags map for this run.",
        }

    total = sum(rg_spend.values())
    allocated = sum(
        cost for rg, cost in rg_spend.items()
        if _tag_has_all(rg_tags.get(rg) or {}, required)
    )
    pct = round(100.0 * allocated / total, 1) if total else None
    covered_rgs = sum(1 for rg in rg_spend if rg in rg_tags)
    return {
        "value": pct, "unit": "percent", "method": "resourceGroupJoin",
        "note": (
            f"Covers only the {len(rg_spend)} resource group(s) present in spend.json's cost "
            f"breakdown ({covered_rgs} of which have resourceGroupTags data) -- not necessarily "
            "the whole subscription if spend.json's breakdown is a top-N list."
        ),
    }


def compute_savings_kpis(ledger: dict) -> tuple[dict, dict]:
    totals = ledger.get("totals", {})
    currency = ledger.get("currency", "AUD")
    estimated = float(totals.get("estimatedMonthly", 0) or 0)
    realised = float(totals.get("realisedMonthly", 0) or 0)

    estimated_note = "Primary currency only."
    if ledger.get("mixedCurrencies"):
        estimated_note += (
            " This run mixes currencies -- see reports/savings-ledger.json's byCurrency for the rest."
        )
    estimated_kpi = {
        "value": round(estimated, 2), "unit": "currency", "currency": currency,
        "note": estimated_note,
    }
    rate = round(100.0 * realised / estimated, 1) if estimated > 0 else 0.0
    realised_kpi = {
        "value": rate, "unit": "percent", "currency": currency,
        "note": "realisedMonthly / estimatedMonthly for the primary currency; 0 when nothing is estimated yet.",
    }
    return estimated_kpi, realised_kpi


def _previous_run(runs_dir: Path | None, run_folder: Path) -> Path | None:
    if not runs_dir or not runs_dir.is_dir():
        return None
    run_name = run_folder.resolve().name
    earlier = sorted(p.name for p in runs_dir.iterdir() if p.is_dir() and p.name < run_name)
    return (runs_dir / earlier[-1]) if earlier else None


def compute_anomaly_kpi(run_folder: Path, runs_dir: Path | None) -> dict:
    findings = list(_iter_findings(run_folder / "findings"))
    count = sum(1 for f in findings if f.get("type") == "anomaly")

    prev = _previous_run(runs_dir, run_folder)
    if prev is None:
        return {
            "value": count, "unit": "count", "previousRunId": None, "previousValue": None,
            "delta": None, "trend": "unavailable",
            "note": "No earlier run found in the runs directory to trend against.",
        }

    prev_count = sum(1 for f in _iter_findings(prev / "findings") if f.get("type") == "anomaly")
    delta = count - prev_count
    trend = "flat" if delta == 0 else ("up" if delta > 0 else "down")
    return {
        "value": count, "unit": "count", "previousRunId": prev.name, "previousValue": prev_count,
        "delta": delta, "trend": trend,
        "note": f"Compared against the nearest earlier run ({prev.name}) in the same runs directory.",
    }


def build_kpis(run_folder: Path, runs_dir: Path | None = None) -> dict:
    inventory = load_json(run_folder / "inventory.json")
    spend = load_json(run_folder / "spend.json")
    ledger = _build_ledger(run_folder)
    required = _required_tags(run_folder)
    estimated_kpi, realised_kpi = compute_savings_kpis(ledger)

    return {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runId": run_folder.resolve().name,
        "currency": ledger.get("currency", "AUD"),
        "mixedCurrencies": bool(ledger.get("mixedCurrencies")),
        "requiredTags": required,
        "kpis": {
            "taggingCompliance": compute_tagging_compliance(inventory, required),
            "allocationCoverage": compute_allocation_coverage(inventory, spend, required),
            "estimatedSavingsOpportunity": estimated_kpi,
            "realisedSavingsRate": realised_kpi,
            "anomalyCount": compute_anomaly_kpi(run_folder, runs_dir),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_folder", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--runs-dir", type=Path, default=None,
        help="Directory containing sibling runs, for the anomalyCount trend. Defaults to the "
             "run folder's own parent directory.",
    )
    args = parser.parse_args()

    if not args.run_folder.is_dir():
        print(f"ERROR: run folder not found: {args.run_folder}")
        return 2

    runs_dir = args.runs_dir or args.run_folder.resolve().parent
    kpis = build_kpis(args.run_folder, runs_dir)
    out = args.out or (args.run_folder / "reports" / "kpis.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(kpis, fh, indent=2)
        fh.write("\n")
    print(json.dumps(kpis, indent=2))
    print(f"\nKPIs written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
