#!/usr/bin/env python3
import ast
import sys
from pathlib import Path

TARGETS = {("pytest", "mark", "skip"), ("pytest", "mark", "xfail")}
SKIP_DIRS = {
    ".git",
    ".mcp",
    ".venv",
    "venv",
    "node_modules",
    "extensions",
    ".pytest_cache",
    "tests",
}


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts & SKIP_DIRS)


def attr_chain(node: ast.AST):
    # Yield dotted attribute chain as tuple of names, e.g. pytest.mark.skip -> ("pytest","mark","skip")
    chain = []
    cur = node
    while isinstance(cur, ast.Attribute):
        chain.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        chain.append(cur.id)
        return tuple(reversed(chain))
    return None


def contains_forbidden_calls(tree: ast.AST) -> bool:
    for n in ast.walk(tree):
        # Direct calls: pytest.mark.skip(...)
        if isinstance(n, ast.Call):
            tgt = n.func
            ch = attr_chain(tgt)
            if ch and ch in TARGETS:
                return True
        # Decorators: @pytest.mark.skip / @pytest.mark.xfail
        if isinstance(n, ast.FunctionDef) or isinstance(n, ast.ClassDef):
            for d in n.decorator_list:
                ch = attr_chain(d)
                if ch and ch in TARGETS:
                    return True
    return False


def iter_pkg_files(root: Path):
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
    for fp in iter_pkg_files(root):
        try:
            src = fp.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src, filename=str(fp))
        except Exception:
            continue
        if contains_forbidden_calls(tree):
            bad.append(fp)
    if bad:
        print("[mcp] Found skip/xfail markers in package code (disallowed):")
        for b in bad[:50]:
            print(" -", b.as_posix())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
