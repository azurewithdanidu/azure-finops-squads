#!/usr/bin/env python3
"""Check one finding before remediation. This does not verify human consent or open a PR."""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

VALIDATOR = Path(__file__).with_name("validate-findings.py")


def decision(finding: dict, confirmed: bool, confirmed_t2: bool) -> tuple[str, str]:
    if finding["tier"] == "T3":
        return "refuse", "T3 findings are analysis-only"
    if finding["status"] != "approved":
        return "refuse", "finding is not approved"
    if not confirmed:
        return "refuse", "explicit user confirmation is required"
    match = finding["iacMatch"]["status"]
    if match == "not-found":
        return "refuse", "IaC source was not located"
    if match == "unmanaged":
        return "manual", "document a manual change request; do not open a PR"
    if not all(
        isinstance(finding["iacMatch"].get(key), str) and finding["iacMatch"][key].strip()
        for key in ("repo", "path")
    ):
        return "refuse", "found IaC match must name the repository and path"
    if finding["tier"] == "T2":
        if not confirmed_t2:
            return "refuse", "T2 requires separate explicit confirmation"
        return "draft", "T2 requires a draft PR"
    return "pr", "finding is eligible for a PR"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="finding JSON file")
    parser.add_argument("--id", required=True, help="finding ID to check")
    parser.add_argument("--confirmed", action="store_true", help="user explicitly confirmed this finding")
    parser.add_argument("--confirmed-t2", action="store_true", help="user separately confirmed T2")
    args = parser.parse_args()

    try:
        with args.path.open(encoding="utf-8") as file:
            document = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"REFUSE: cannot read finding file: {exc}", file=sys.stderr)
        return 1
    spec = importlib.util.spec_from_file_location("validate_findings", VALIDATOR)
    if spec is None or spec.loader is None:
        print("REFUSE: finding validator could not be loaded", file=sys.stderr)
        return 1
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    errors = validator.validate_document(document, validator.FINDING_SCHEMA)
    if errors:
        print("REFUSE: finding file did not pass schema validation: " + "; ".join(errors),
              file=sys.stderr)
        return 1
    items = validator.iter_items(document)
    matches = [item for item in items if item.get("id") == args.id]
    if len(matches) != 1:
        print("REFUSE: finding ID must match exactly one record", file=sys.stderr)
        return 1
    outcome, reason = decision(matches[0], args.confirmed, args.confirmed_t2)
    print(f"{outcome.upper()}: {reason}")
    return 1 if outcome == "refuse" else 0


if __name__ == "__main__":
    raise SystemExit(main())
