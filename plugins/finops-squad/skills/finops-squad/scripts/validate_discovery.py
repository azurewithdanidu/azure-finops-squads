#!/usr/bin/env python3
"""Validate Discovery's output (inventory.json, spend.json, advisor.json) for a run folder.

Usage:
    python scripts/validate_discovery.py <run-folder-or-runs-folder> [...] [--strict]

Each path is either one run folder (containing inventory.json / spend.json / advisor.json) or a
folder of run folders. Discovery runs this before hand-off.

- ERRORS mean the data is malformed (bad JSON, wrong types, inconsistent numbers). Exit code 1.
- WARNINGS mean a required enrichment is missing: the daily spend series, `tagCoverage
  .fullyTaggedCount` or `resourceGroupTags` (each is acceptable only if recorded in
  inventory.json `enrichmentSkipped` with a reason). Exit code 0, or 1 with --strict.

Legacy files stay valid: every enrichment is optional in the schema, so older run folders load
(they just produce warnings). This script only reads files; it never calls Azure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import spend_daily as sd

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
SPEND_SCHEMA = SCHEMA_DIR / "spend.schema.json"
KNOWN_ENRICHMENTS = {"fullyTaggedCount", "resourceGroupTags", "daily"}
MAX_NAMED_SERVICES = 10  # the daily series keeps the top 10 services plus "Other"

try:
    import jsonschema  # type: ignore

    HAVE_JSONSCHEMA = True
except ImportError:  # pragma: no cover
    HAVE_JSONSCHEMA = False

Report = tuple[list[str], list[str]]  # (errors, warnings)


def _schema_errors(doc, schema_path: Path) -> list[str]:
    if not HAVE_JSONSCHEMA:  # pragma: no cover
        return ["jsonschema is required for spend schema validation"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    return [
        f"{'/'.join(str(p) for p in e.path) or '(root)'}: {e.message}"
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    ]


# ---------------------------------------------------------------------------------- spend
def validate_spend(doc, skipped_fields: frozenset | set = frozenset()) -> Report:
    """`skipped_fields` are the inventory.json `enrichmentSkipped` fields (a skipped daily series
    with a recorded reason is accepted without a warning)."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(doc, dict):
        return ["spend.json must be a JSON object"], warnings
    errors.extend(_schema_errors(doc, SPEND_SCHEMA))

    status = doc.get("status")
    if status == "unavailable":
        if not doc.get("reason"):
            errors.append("status is 'unavailable' but no 'reason' (the real error) was recorded")
        return errors, warnings  # nothing else to enrich

    if "daily" not in doc:
        if "daily" not in skipped_fields:
            warnings.append(
                "daily spend series not captured (spend.daily): re-run the Daily-grain "
                "arm.query_costs call, or record why in inventory.json enrichmentSkipped"
            )
        return errors, warnings
    if errors and any(e.startswith("daily") for e in errors):
        return errors, warnings  # structurally broken: semantic checks would just add noise

    daily = sd.get_daily(doc)
    if daily is None:
        errors.append("daily: block is present but unusable (needs from, to, series, dailyTotal)")
        return errors, warnings
    start, end = sd.window(daily)
    if end < start:
        errors.append("daily: 'to' is before 'from'")
        return errors, warnings

    def in_window(label: str, rows: list) -> None:
        bad = [r for r in rows if isinstance(r, dict) and not (
            (d := sd.parse_date(r.get("date"))) is not None and start <= d <= end)]
        if bad:
            errors.append(f"daily.{label}: {len(bad)} row(s) have a date outside {start}..{end}")

    in_window("series", daily["series"])
    in_window("dailyTotal", daily["dailyTotal"])

    seen_total, dup_total = set(), 0
    for r in daily["dailyTotal"]:
        key = r.get("date") if isinstance(r, dict) else None
        dup_total += key in seen_total
        seen_total.add(key)
    if dup_total:
        errors.append(f"daily.dailyTotal: {dup_total} duplicate date(s)")

    seen_pair, dup_pair = set(), 0
    for r in daily["series"]:
        if isinstance(r, dict):
            pair = (r.get("date"), r.get("service"))
            dup_pair += pair in seen_pair
            seen_pair.add(pair)
    if dup_pair:
        errors.append(f"daily.series: {dup_pair} duplicate (date, service) row(s)")

    by_service = sd.series_by_service(daily)
    named = [s for s in by_service if s != sd.OTHER]
    if len(named) > MAX_NAMED_SERVICES:
        errors.append(
            f"daily.series: {len(named)} named services; keep the top {MAX_NAMED_SERVICES} and "
            f"fold the rest into '{sd.OTHER}'"
        )

    prov = sd.parse_date(daily.get("provisionalFrom"))
    if daily.get("provisionalFrom") and (prov is None or not (start <= prov <= end)):
        errors.append("daily.provisionalFrom: must be a date inside the daily window")

    if daily.get("currency") and doc.get("currency") and daily["currency"] != doc["currency"]:
        errors.append(
            f"daily.currency {daily['currency']} differs from spend currency {doc['currency']}"
        )

    # The per-service series must add up to the all-services total, day by day.
    totals = sd.total_by_date(daily)
    sums: dict = {}
    for svc_days in by_service.values():
        for d, cost in svc_days.items():
            sums[d] = sums.get(d, 0.0) + cost
    off = [
        d for d, total in totals.items()
        if abs(sums.get(d, 0.0) - total) > max(0.01, sd.RECONCILE_TOLERANCE * abs(total))
    ]
    if off:
        errors.append(
            f"daily: per-service series do not add up to dailyTotal on {len(off)} day(s) "
            f"(first: {min(off)})"
        )

    rec = sd.reconcile(doc)
    if rec["status"] == "mismatch":
        warnings.append(
            f"daily total {rec['dailySum']:,.2f} differs from the period total "
            f"{rec['aggregateTotal']:,.2f} by {rec['deltaPct']}% (tolerance "
            f"{sd.RECONCILE_TOLERANCE:.0%}) — check the window and metric match the aggregate call"
        )
    elif rec["status"] == "skipped" and rec["reason"] not in ("no daily data",):
        warnings.append(f"daily series not reconciled: {rec['reason']}")
    if daily.get("truncated"):
        warnings.append("daily.truncated is true: the query hit its row limit; the series is incomplete")
    return errors, warnings


# ------------------------------------------------------------------------------ inventory
def validate_inventory(doc) -> Report:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(doc, dict):
        return ["inventory.json must be a JSON object"], warnings

    resources = doc.get("resources")
    has_resources = isinstance(resources, list) and bool(resources)
    if "resources" in doc:
        if not isinstance(resources, list):
            errors.append("resources: must be an array")
        else:
            bad = [r for r in resources if not (isinstance(r, dict) and r.get("id"))]
            if bad:
                errors.append(f"resources: {len(bad)} item(s) without an 'id'")

    cov = doc.get("tagCoverage")
    if "tagCoverage" in doc:
        if not isinstance(cov, dict):
            errors.append("tagCoverage: must be an object")
        else:
            total = cov.get("total")
            if not isinstance(total, int) or isinstance(total, bool) or total <= 0:
                errors.append("tagCoverage.total: must be a positive integer")
            else:
                for key, val in cov.items():
                    if key == "total":
                        continue
                    if key == "fullyTaggedCount" or key.startswith("missing"):
                        if not isinstance(val, int) or isinstance(val, bool) or not 0 <= val <= total:
                            errors.append(f"tagCoverage.{key}: must be an integer from 0 to {total}")

    rg_tags = doc.get("resourceGroupTags")
    if "resourceGroupTags" in doc:
        if not isinstance(rg_tags, dict) or not all(isinstance(v, dict) for v in rg_tags.values()):
            errors.append("resourceGroupTags: must map each resource group name to an object of tags")

    skipped = doc.get("enrichmentSkipped")
    skipped_fields: set[str] = set()
    if "enrichmentSkipped" in doc:
        if not isinstance(skipped, list):
            errors.append("enrichmentSkipped: must be an array of {field, reason}")
        else:
            for i, item in enumerate(skipped):
                ok = (
                    isinstance(item, dict)
                    and isinstance(item.get("field"), str) and item["field"].strip()
                    and isinstance(item.get("reason"), str) and item["reason"].strip()
                )
                if not ok:
                    errors.append(f"enrichmentSkipped[{i}]: needs a non-empty 'field' and 'reason'")
                    continue
                skipped_fields.add(item["field"])
                if item["field"] not in KNOWN_ENRICHMENTS:
                    warnings.append(
                        f"enrichmentSkipped[{i}]: unknown field '{item['field']}' "
                        f"(known: {', '.join(sorted(KNOWN_ENRICHMENTS))})"
                    )

    have_fully = isinstance(cov, dict) and cov.get("fullyTaggedCount") is not None
    if not have_fully and not has_resources and "fullyTaggedCount" not in skipped_fields:
        warnings.append(
            "tagCoverage.fullyTaggedCount missing: required (unless skipped with a reason in "
            "enrichmentSkipped) — tagging compliance is otherwise only an approximation"
        )
    if "resourceGroupTags" not in doc and "resourceGroupTags" not in skipped_fields:
        warnings.append(
            "resourceGroupTags missing: required (unless skipped with a reason in "
            "enrichmentSkipped) — allocation coverage cannot be computed without it"
        )
    if have_fully and "fullyTaggedCount" in skipped_fields:
        warnings.append("fullyTaggedCount is recorded as skipped but is present")
    if "resourceGroupTags" in doc and "resourceGroupTags" in skipped_fields:
        warnings.append("resourceGroupTags is recorded as skipped but is present")
    return errors, warnings


# --------------------------------------------------------------------------------- advisor
def validate_advisor(doc) -> Report:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(doc, dict):
        return ["advisor.json must be a JSON object"], warnings
    recs, summary = doc.get("recommendations"), doc.get("summary")
    if not isinstance(recs, list) and not isinstance(summary, list):
        errors.append("needs a 'recommendations' array (or a 'summary' array of recommendations)")
    for label, rows in (("recommendations", recs), ("summary", summary)):
        if isinstance(rows, list) and not all(isinstance(r, dict) for r in rows):
            errors.append(f"{label}: every item must be an object")
    total = doc.get("totalCostRecommendations")
    if total is not None and (not isinstance(total, int) or isinstance(total, bool) or total < 0):
        errors.append("totalCostRecommendations: must be a non-negative integer")
    if not doc.get("capturedAt"):
        warnings.append("capturedAt missing")
    return errors, warnings


# ------------------------------------------------------------------------------------ run
VALIDATORS = {
    "inventory.json": validate_inventory,
    "spend.json": validate_spend,
    "advisor.json": validate_advisor,
}


def _skipped_fields(run: Path) -> set[str]:
    """Fields recorded in inventory.json `enrichmentSkipped` (empty if absent or unreadable)."""
    try:
        doc = json.loads((run / "inventory.json").read_text(encoding="utf-8"))
        items = doc.get("enrichmentSkipped") if isinstance(doc, dict) else None
        return {
            i["field"] for i in items or []
            if isinstance(i, dict) and isinstance(i.get("field"), str) and i.get("reason")
        }
    except (OSError, ValueError):
        return set()


def validate_run(run: Path) -> dict[str, Report]:
    """Validate the three Discovery artifacts of one run folder."""
    out: dict[str, Report] = {}
    skipped = _skipped_fields(run)
    for name, fn in VALIDATORS.items():
        path = run / name
        if not path.is_file():
            out[name] = ([f"{name} is missing"], [])
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            out[name] = ([f"invalid JSON: {exc}"], [])
            continue
        out[name] = fn(doc, skipped) if name == "spend.json" else fn(doc)
    return out


def _run_folders(path: Path) -> list[Path]:
    if any((path / n).exists() for n in VALIDATORS):
        return [path]
    return sorted(p for p in path.iterdir() if p.is_dir()) if path.is_dir() else []


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    strict = "--strict" in argv[1:]
    if not args:
        print(__doc__)
        return 2
    n_err = n_warn = 0
    for arg in args:
        path = Path(arg)
        folders = _run_folders(path)
        if not folders:
            print(f"ERROR  {path}: no run folder found")
            n_err += 1
        for run in folders:
            for name, (errs, warns) in validate_run(run).items():
                label = f"{run}/{name}"
                for e in errs:
                    print(f"ERROR  {label}: {e}")
                for w in warns:
                    print(f"WARN   {label}: {w}")
                if not errs and not warns:
                    print(f"OK     {label}")
                n_err += len(errs)
                n_warn += len(warns)
    print(f"\n{n_err} error(s), {n_warn} warning(s)" + (" (strict)" if strict else ""))
    return 1 if n_err or (strict and n_warn) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
