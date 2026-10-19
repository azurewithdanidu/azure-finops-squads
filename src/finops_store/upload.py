"""Upload local run folders to the finops blob container.

Usage:
    python -m finops_store.upload --subscription <id> --source .finops/runs \
        --account-url https://<account>.blob.core.windows.net [--container finops] [--dry-run]

Findings and verification files are schema-validated before upload; failures are reported and
skipped (exit code 1).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .store import BlobBackend, RunStore, StoreError, ValidationError


def upload_runs(source: Path, subscription_id: str, backend, dry_run: bool = False) -> tuple[int, list[str]]:
    uploaded = 0
    failures: list[str] = []
    for run_dir in sorted(p for p in source.iterdir() if p.is_dir()):
        try:
            store = RunStore(backend, subscription_id, run_dir.name)
        except StoreError as exc:
            failures.append(f"{run_dir.name}: {exc}")
            continue
        for file in sorted(f for f in run_dir.rglob("*") if f.is_file()):
            rel = file.relative_to(run_dir).as_posix()
            try:
                if dry_run:
                    store.key(rel)
                elif file.suffix == ".json":
                    import json

                    store.write_json(rel, json.loads(file.read_text(encoding="utf-8")))
                else:
                    store.write_text(rel, file.read_text(encoding="utf-8"))
                uploaded += 1
            except (ValidationError, StoreError, ValueError) as exc:
                failures.append(f"{run_dir.name}/{rel}: {exc}")
    return uploaded, failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subscription", required=True)
    ap.add_argument("--source", type=Path, default=Path(".finops/runs"))
    ap.add_argument("--account-url", required=True)
    ap.add_argument("--container", default="finops")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    backend = BlobBackend(args.account_url, args.container)
    uploaded, failures = upload_runs(args.source, args.subscription, backend, args.dry_run)
    for f in failures:
        print(f"FAIL {f}", file=sys.stderr)
    print(f"{'would upload' if args.dry_run else 'uploaded'} {uploaded} file(s), {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
