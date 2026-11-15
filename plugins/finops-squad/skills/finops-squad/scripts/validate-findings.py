#!/usr/bin/env python3
"""Validate FinOps Squad artifacts against the JSON schemas.

Usage:
    python scripts/validate-findings.py <path> [<path> ...]

Each <path> may be a file or a directory. Directories are searched recursively.
Files under a 'findings/' location or named 'findings.json'/'waste.json' etc. are
validated against finding.schema.json (array of findings OR a single finding).
Files under 'verification/' are validated against verification.schema.json.

Exit code 0 => all valid. Non-zero => at least one failure (details printed).

Dependency: jsonschema (pip install jsonschema). Validation fails if it is missing
or if no matching artifacts are found.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
FINDING_SCHEMA = SCHEMA_DIR / "finding.schema.json"
VERIFICATION_SCHEMA = SCHEMA_DIR / "verification.schema.json"

try:
    import jsonschema  # type: ignore

    HAVE_JSONSCHEMA = True
except ImportError:  # pragma: no cover
    HAVE_JSONSCHEMA = False


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def pick_schema(path: Path) -> Path | None:
    parts = {p.lower() for p in path.parts}
    name = path.name.lower()
    if "verification" in parts or name.startswith("verification"):
        return VERIFICATION_SCHEMA
    if "findings" in parts or name in {
        "findings.json",
        "waste.json",
        "rightsizing.json",
        "tagging.json",
        "commitments.json",
        "anomalies.json",
    }:
        return FINDING_SCHEMA
    return None


def iter_items(doc):
    """A finding/verification file may be a single object or an array of them."""
    if isinstance(doc, list):
        yield from doc
    elif isinstance(doc, dict) and "findings" in doc and isinstance(doc["findings"], list):
        yield from doc["findings"]
    else:
        yield doc


def artifact_format_checker():
    checker = jsonschema.FormatChecker()

    @checker.checks("date", raises=ValueError)
    def valid_date(value):
        if not isinstance(value, str):
            return True
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)) and bool(date.fromisoformat(value))

    @checker.checks("date-time", raises=ValueError)
    def valid_datetime(value):
        if not isinstance(value, str):
            return True
        pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
        return bool(re.fullmatch(pattern, value)) and bool(datetime.fromisoformat(value))

    return checker


def validate_document(doc, schema_path: Path) -> list[str]:
    errors: list[str] = []
    if not HAVE_JSONSCHEMA:
        return ["jsonschema is required for validation"]
    schema = load_json(schema_path)
    validator = jsonschema.Draft7Validator(schema, format_checker=artifact_format_checker())
    for idx, item in enumerate(iter_items(doc)):
        prefix = f"[item {idx}] "
        for err in sorted(validator.iter_errors(item), key=lambda e: list(map(str, e.path))):
            loc = "/".join(str(p) for p in err.path) or "(root)"
            errors.append(f"{prefix}{loc}: {err.message}")
    return errors


def validate_file(path: Path, schema_path: Path) -> list[str]:
    try:
        doc = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read JSON: {exc}"]
    return validate_document(doc, schema_path)


def collect_targets(path: Path) -> list[Path]:
    if path.is_dir():
        return [p for p in path.rglob("*.json") if pick_schema(p)]
    return [path]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    if not HAVE_JSONSCHEMA:
        print("ERROR: 'jsonschema' is required; install with: pip install jsonschema",
              file=sys.stderr)
        return 2

    total = 0
    failed = 0
    for arg in argv[1:]:
        root = Path(arg)
        if not root.exists():
            print(f"FAIL  {root}: path does not exist")
            failed += 1
            continue
        for target in collect_targets(root):
            schema_path = pick_schema(target)
            if schema_path is None:
                continue
            total += 1
            errs = validate_file(target, schema_path)
            if errs:
                failed += 1
                print(f"FAIL  {target}")
                for e in errs:
                    print(f"        - {e}")
            else:
                print(f"OK    {target}  [{schema_path.name}]")

    if total == 0:
        print("No findings/verification JSON files found to validate.")
        return 1
    print(f"\n{total - failed}/{total} file(s) valid.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
