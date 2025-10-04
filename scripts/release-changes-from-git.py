#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def previous_tag() -> str | None:
    # Try previous tag relative to HEAD
    try:
        return run(["git", "describe", "--tags", "--abbrev=0", "HEAD^"])
    except Exception:
        # Fallback: second most recent tag by creation date
        try:
            tags = run(["bash", "-lc", "git tag --sort=-creatordate | sed -n '2p'"])
            return tags or None
        except Exception:
            return None


def collect_commits(rng: str | None) -> list[tuple[str, str, str]]:
    fmt = "%H\x01%an\x01%s"
    cmd = ["git", "log", "--no-merges", f"--pretty=format:{fmt}"]
    if rng:
        cmd.append(rng)
    out = run(cmd)
    commits: list[tuple[str, str, str]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        try:
            h, a, s = line.split("\x01", 2)
        except ValueError:
            continue
        commits.append((h.strip(), a.strip(), s.strip()))
    return commits


CATS = [
    "feat",
    "fix",
    "docs",
    "perf",
    "refactor",
    "test",
    "build",
    "ci",
    "chore",
]


def categorize(subject: str) -> str:
    m = re.match(r"^(\w+)(\(.+?\))?:\s", subject)
    if m:
        t = m.group(1).lower()
        if t in CATS:
            return t
    return "other"


def main() -> None:
    out_path = Path(".mcp/dashboard/release_changes.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prev = previous_tag()
    rng = f"{prev}..HEAD" if prev else None
    commits = collect_commits(rng)
    if not commits:
        out_path.write_text("(no changes detected)\n", encoding="utf-8")
        print(str(out_path))
        return
    buckets: dict[str, list[tuple[str, str, str]]] = {c: [] for c in CATS + ["other"]}
    for h, a, s in commits:
        buckets[categorize(s)].append((h, a, s))
    lines: list[str] = []
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    for c in [*CATS, "other"]:
        items: list[tuple[str, str, str]] = buckets.get(c) or []
        if not items:
            continue
        lines.append(f"## {c}")
        for h, a, s in items:
            pr_link = ""
            m = re.search(r"\(#(\d+)\)", s)
            if m and repo:
                pr_link = f" https://github.com/{repo}/pull/{m.group(1)}"
            author = f" by {a}" if a else ""
            lines.append(f"- {s}{author} ({h[:7]}){pr_link}")
        lines.append("")
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
