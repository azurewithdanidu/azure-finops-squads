#!/usr/bin/env python3
"""Compare findings in two run folders without contacting Azure."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from ledger import iter_findings


def compare_runs(findings_a: list[dict], findings_b: list[dict]) -> dict[str, list[dict]]:
    """Match earlier and later findings by type and resource ID, not per-run ID."""
    earlier = {(f.get("type"), f.get("resourceId")): f for f in findings_a}
    later = {(f.get("type"), f.get("resourceId")): f for f in findings_b}
    return {
        "resolved": [earlier[key] for key in sorted(earlier.keys() - later.keys(), key=str)],
        "new": [later[key] for key in sorted(later.keys() - earlier.keys(), key=str)],
        "recurring": [later[key] for key in sorted(earlier.keys() & later.keys(), key=str)],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("earlier", type=Path)
    parser.add_argument("later", type=Path)
    args = parser.parse_args()
    validator = Path(__file__).with_name("validate-findings.py")
    for run in (args.earlier, args.later):
        result = subprocess.run(
            [sys.executable, str(validator), str(run / "findings")],
            capture_output=True, text=True, check=False,
        )
        if result.returncode:
            print(f"ERROR: cannot compare {run}: {result.stdout}{result.stderr}", file=sys.stderr)
            return 1
    print(json.dumps(compare_runs(
        list(iter_findings(args.earlier / "findings")),
        list(iter_findings(args.later / "findings")),
    ), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
