#!/usr/bin/env python3
"""Validate .github/skills so each skill can be uploaded to Foundry as a self-contained unit.

Checks per skill folder:
  * SKILL.md exists with YAML front matter containing name and description
  * name matches the folder name; name/description values are unquoted (quotes break Foundry import)
  * description is non-empty and states when to use the skill
  * every relative markdown link resolves inside the skill folder, or to a sibling skill's SKILL.md
    or references/ file (siblings travel together in the same toolbox)

Usage: python scripts/validate-skills.py [skills_dir]
Exit code 0 = valid, 1 = problems found.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
FRONT_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)


def parse_front_matter(text: str) -> dict[str, str] | None:
    m = FRONT_RE.match(text)
    if not m:
        return None
    fields: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def check_links(skill_dir: Path, skills_root: Path) -> list[str]:
    problems: list[str] = []
    for md in skill_dir.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            if re.match(r"^(https?:|mailto:|#)", target):
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            resolved = (md.parent / path_part).resolve()
            rel = md.relative_to(skill_dir)
            try:
                resolved.relative_to(skill_dir.resolve())
                inside = True
            except ValueError:
                inside = False
            if inside:
                if not resolved.exists():
                    problems.append(f"{rel}: broken link {target}")
                continue
            try:
                parts = resolved.relative_to(skills_root.resolve()).parts
            except ValueError:
                problems.append(f"{rel}: link escapes the skills folder: {target}")
                continue
            if not resolved.exists():
                problems.append(f"{rel}: broken link {target}")
            elif parts[1:2] and parts[1] not in ("SKILL.md", "references"):
                problems.append(f"{rel}: link to non-portable sibling file: {target}")
    return problems


def validate(skills_root: Path) -> list[str]:
    problems: list[str] = []
    dirs = sorted(p for p in skills_root.iterdir() if p.is_dir())
    if not dirs:
        return [f"no skills found in {skills_root}"]
    for d in dirs:
        skill_md = d / "SKILL.md"
        if not skill_md.exists():
            problems.append(f"{d.name}: missing SKILL.md")
            continue
        fm = parse_front_matter(skill_md.read_text(encoding="utf-8"))
        if fm is None:
            problems.append(f"{d.name}: missing YAML front matter")
            continue
        for key in ("name", "description"):
            value = fm.get(key, "")
            if not value:
                problems.append(f"{d.name}: front matter '{key}' is missing or empty")
            elif value[0] in "\"'":
                problems.append(f"{d.name}: front matter '{key}' must be unquoted")
        if fm.get("name") and fm["name"] != d.name:
            problems.append(f"{d.name}: name '{fm['name']}' does not match folder")
        if fm.get("description") and "use " not in fm["description"].lower():
            problems.append(f"{d.name}: description should say when to use the skill")
        problems += [f"{d.name}/{p}" for p in check_links(d, skills_root)]
    return problems


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".github/skills")
    problems = validate(root)
    for p in problems:
        print(f"ERROR {p}")
    count = sum(1 for p in root.iterdir() if p.is_dir())
    print(f"{count} skills checked, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
