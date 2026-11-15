#!/usr/bin/env python3
"""Generate client manifests and run the agentz gate in an isolated local marketplace."""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "finops-squad"
GENERATED = (".claude-plugin/plugin.json", ".cursor-plugin/plugin.json", "mcp.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agentz-root", type=Path, required=True, help="local agentz checkout")
    parser.add_argument("--sync", action="store_true", help="update generated plugin client files")
    args = parser.parse_args()
    tooling = args.agentz_root.resolve() / "scripts"
    required = ("marketplace_lib.py", "sync_manifests.py", "build_catalog.py", "validate_repo.py")
    if not all((tooling / name).is_file() for name in required):
        parser.error("--agentz-root must contain the agentz marketplace scripts")

    manifest = json.loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="finops-marketplace-") as temporary:
        stage = Path(temporary)
        packaged = stage / "plugins" / "finops-squad"
        shutil.copytree(PLUGIN, packaged, ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", ".finops", "node_modules"
        ))
        (stage / "scripts").mkdir()
        for name in required:
            shutil.copyfile(tooling / name, stage / "scripts" / name)
        registry = {
            "name": "finops-local-validation",
            "owner": manifest["author"],
            "plugins": [{
                "name": "finops-squad",
                "source": "./plugins/finops-squad",
                "description": manifest["description"],
                "category": "observability",
            }],
        }
        (stage / ".claude-plugin").mkdir()
        (stage / ".claude-plugin" / "marketplace.json").write_text(
            json.dumps(registry, indent=2) + "\n", encoding="utf-8"
        )
        (stage / ".github").mkdir()
        (stage / ".github" / "CODEOWNERS").write_text(
            "/plugins/finops-squad/ @azurewithdanidu\n", encoding="utf-8"
        )
        (stage / "README.md").write_text(
            "# Local validation\n\n<!-- plugins-table:start -->\n<!-- plugins-table:end -->\n",
            encoding="utf-8",
        )
        for name in required[1:]:
            result = subprocess.run(
                [sys.executable, str(stage / "scripts" / name)], cwd=stage, check=False
            )
            if result.returncode:
                return result.returncode
        stale = []
        for name in GENERATED:
            expected = packaged / name
            target = PLUGIN / name
            if not expected.exists():
                if target.exists():
                    stale.append(name)
                    if args.sync:
                        target.unlink()
                continue
            if target.exists() and target.read_bytes() == expected.read_bytes():
                continue
            stale.append(name)
            if args.sync:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(expected.read_bytes())
        if stale and not args.sync:
            print("Generated plugin files are stale: " + ", ".join(stale), file=sys.stderr)
            print("Repeat with --sync to regenerate using agentz tooling.", file=sys.stderr)
            return 1
    print("Local package gate passed. No remote marketplace registration or publication performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
