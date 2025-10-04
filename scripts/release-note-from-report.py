#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


def read_version() -> str:
    # Prefer pyproject.toml version
    p = Path("pyproject.toml")
    if p.exists():
        m = re.search(
            r"^version\s*=\s*\"([^\"]+)\"", p.read_text(encoding="utf-8"), re.M
        )
        if m:
            return m.group(1)
    # Fallback to package __init__
    pi = Path("mcp_rules_assistant/__init__.py").read_text(encoding="utf-8")
    m = re.search(r"__version__\s*=\s*\"([^\"]+)\"", pi)
    return m.group(1) if m else "0.0.0"


def summarize_report(path: Path) -> list[str]:
    if not path.exists():
        return ["Release report not found: " + str(path)]
    txt = path.read_text(encoding="utf-8")
    lines = []
    # Extract quick statuses
    for key in (
        "Python tests + coverage",
        "Coverage weak files (policy)",
        "VS Code lcov gate (80%)",
        "License harden verify",
        "Python package build + twine check",
    ):
        m = re.search(rf"- {re.escape(key)}:\s*(\w+)", txt)
        if m:
            lines.append(f"{key}: {m.group(1)}")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate short release note snippet from report"
    )
    ap.add_argument("--report", default=".mcp/dashboard/release_check.md")
    ap.add_argument("--out", default=".mcp/dashboard/release_note_snippet.md")
    args = ap.parse_args()
    version = read_version()
    lines = summarize_report(Path(args.report))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        (
            f"# Release {version}\n\n"
            "Status Summary\n"
            + "\n".join(f"- {line}" for line in lines)
            + "\n\nNotes\n- See full report in release_check.md\n"
        ),
        encoding="utf-8",
    )
    print(str(out))


if __name__ == "__main__":
    main()
