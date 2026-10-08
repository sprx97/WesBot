#!/usr/bin/env python3
"""Regenerate requirements.txt from third-party imports in project Python files."""

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAMES = {
    "challonge": "pychallonge",
    "discord": "discord.py",
    "google": "google-auth",
    "googleapiclient": "google-api-python-client",
    "lxml": "lxml",
    "pymysql": "PyMySQL",
    "pytz": "pytz",
    "requests": "requests",
}
LOCAL_MODULES = {"Config", "Cogs", "Shared"}
REQUIREMENT = re.compile(r"^([A-Za-z0-9_.-]+)(.*)$")


def source_files():
    yield from ROOT.glob("*.py")
    yield from (ROOT / "Cogs").rglob("*.py")


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".", 1)[0]


def existing_versions():
    versions = {}
    req_file = ROOT / "requirements.txt"
    if not req_file.exists():
        return versions
    for line in req_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(("-", ".", "/")):
            continue
        match = REQUIREMENT.match(line)
        if match:
            versions[match.group(1).lower().replace("_", "-")] = match.group(2)
    return versions


def main():
    imported = set()
    for path in source_files():
        imported.update(imported_modules(path))

    distributions = {
        PACKAGE_NAMES[module]
        for module in imported
        if module in PACKAGE_NAMES and module not in LOCAL_MODULES
    }
    old_versions = existing_versions()
    lines = []
    for distribution in sorted(distributions, key=str.lower):
        suffix = old_versions.get(distribution.lower().replace("_", "-"), "")
        lines.append(f"{distribution}{suffix}")

    target = ROOT / "requirements.txt"
    content = "\n".join(lines) + "\n"
    if not target.exists() or target.read_text(encoding="utf-8") != content:
        target.write_text(content, encoding="utf-8")
        print(f"Updated {target.relative_to(ROOT)}")
    else:
        print("requirements.txt is up to date")


if __name__ == "__main__":
    main()
