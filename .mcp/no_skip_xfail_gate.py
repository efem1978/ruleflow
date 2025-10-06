#!/usr/bin/env python3
import sys
from pathlib import Path

PATTERNS = ("pytest.mark.skip", "pytest.mark.xfail")
SKIP_DIRS = {
    ".git",
    ".mcp",
    ".venv",
    "venv",
    "node_modules",
    "extensions",
    ".pytest_cache",
}


def should_skip(p: Path) -> bool:
    parts = set(p.parts)
    if SKIP_DIRS.intersection(parts):
        return True
    # Only scan package code, not tests
    if str(p).startswith("tests/"):
        return True
    return False


def iter_targets(root: Path):
    pkg = root / "mcp_rules_assistant"
    base = [pkg] if pkg.exists() else [root]
    for b in base:
        for fp in b.rglob("*.py"):
            if should_skip(fp):
                continue
            yield fp


def main() -> int:
    root = Path(".").resolve()
    bad = []
    for fp in iter_targets(root):
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if any(pat in text for pat in PATTERNS):
            bad.append(fp)
    if bad:
        print("[mcp] Found skip/xfail markers in package code (disallowed):")
        for b in bad[:50]:
            print(" -", b.as_posix())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
