#!/usr/bin/env python3
"""Check consumer-local configuration and private artifact storage. Never queries Azure."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]


def check_workspace(workspace: Path) -> list[str]:
    if not workspace.is_absolute() or not workspace.is_dir():
        return ["workspace must be an existing absolute directory"]
    workspace = workspace.resolve()
    if workspace.is_relative_to(PLUGIN_ROOT):
        return ["consumer workspace must not be inside the installed plugin"]
    private = workspace / ".finops"
    if not private.resolve().is_relative_to(workspace):
        return [".finops must resolve inside the consumer workspace"]
    config = private / "config.json"
    if not config.is_file():
        return ["consumer .finops/config.json is missing; create it locally before querying Azure"]
    if not config.resolve().is_relative_to(workspace):
        return ["configuration must resolve inside the consumer workspace"]
    try:
        document = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ["consumer configuration is unreadable or invalid JSON (contents suppressed)"]
    if not isinstance(document, dict):
        return ["consumer configuration must be a JSON object"]
    subscriptions = document.get("subscriptions")
    if not isinstance(subscriptions, list) or not subscriptions or not all(
        isinstance(scope, str) and scope.strip() for scope in subscriptions
    ):
        return ["configuration requires a non-empty subscriptions array"]
    iac = document.get("iac")
    if not isinstance(iac, dict) or iac.get("type") != "bicep":
        return ["configuration iac.type must be bicep"]
    try:
        tracked = subprocess.run(
            ["git", "-C", str(workspace), "ls-files", "--", ".finops"],
            capture_output=True, text=True, check=False,
        )
        if tracked.returncode:
            return ["consumer workspace must be inside a Git repository"]
        if tracked.stdout.strip():
            return [".finops contains tracked files; resolve private artifact tracking before running"]
        ignored = subprocess.run(
            ["git", "-C", str(workspace), "check-ignore", "--no-index", "--stdin", "-z"],
            input=".finops/\0.finops/config.json\0.finops/runs/preflight-probe/reports/summary.md\0",
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return ["Git is required for private artifact checks"]
    expected = {".finops/", ".finops/config.json", ".finops/runs/preflight-probe/reports/summary.md"}
    if ignored.returncode != 0 or set(ignored.stdout.rstrip("\0").split("\0")) != expected:
        return [".finops/ must be Git-ignored; ask the user before changing ignore rules"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    errors = check_workspace(args.workspace)
    for error in errors:
        print(f"BLOCKED: {error}", file=sys.stderr)
    if errors:
        return 1
    print("Local preflight passed. Effective Azure read-only permissions still require user confirmation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
