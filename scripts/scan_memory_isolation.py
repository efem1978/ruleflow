#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        return child.resolve().is_relative_to(parent.resolve())  # py311+
    except Exception:
        c = str(child.resolve())
        p = str(parent.resolve())
        return c == p or c.startswith(p + os.sep)


def scan_project(project_root: Path) -> Dict[str, Any]:
    root = project_root.resolve()
    mcp = (root / ".mcp").resolve()
    out: Dict[str, Any] = {"project": str(root), "memory": []}
    if not mcp.exists() or not mcp.is_dir():
        out["note"] = ".mcp missing"
        return out
    targets: List[Path] = []
    targets.append(mcp / "memory.json")
    targets.extend(list(mcp.glob("memory.*.json")))
    for p in targets:
        info: Dict[str, Any] = {"path": str(p.relative_to(root))}
        try:
            if not p.exists() and not p.lstat():
                info["exists"] = False
                out["memory"].append(info)
                continue
        except Exception:
            info["exists"] = False
            out["memory"].append(info)
            continue
        info["exists"] = True
        try:
            st = p.lstat()
            info["is_symlink"] = bool(os.path.islink(p))
            real = p.resolve()
            info["realpath"] = str(real)
            info["inside_mcp"] = _is_inside(real, mcp)
            # hardlink count (best-effort)
            try:
                nlink = int(getattr(st, "st_nlink", 1))
            except Exception:
                nlink = 1
            info["nlink"] = nlink
            issues: List[str] = []
            if info["is_symlink"] and not info["inside_mcp"]:
                issues.append("symlink_outside_mcp")
            if not info["inside_mcp"]:
                issues.append("outside_mcp")
            if nlink and nlink > 1:
                issues.append("hardlink_shared")
            info["issues"] = issues
            info["safe"] = not issues
        except Exception as e:
            info["error"] = str(e)
            info["safe"] = False
        out["memory"].append(info)
    # quick project-level flag
    out["ok"] = all(m.get("safe") for m in out["memory"]) if out["memory"] else True
    return out


def scan_parent(parent: Path) -> Dict[str, Any]:
    base = parent.resolve()
    results: List[Dict[str, Any]] = []
    # include parent itself if it has markers
    cands = [base] + [p for p in base.iterdir() if p.is_dir()]
    for p in cands:
        # heuristic: treat as project if it contains .mcp or common project files
        if (
            (p / ".mcp").exists()
            or (p / "pyproject.toml").exists()
            or (p / "package.json").exists()
        ):
            results.append(scan_project(p))
    summary = {
        "parent": str(base),
        "projects": results,
        "counts": {
            "total": len(results),
            "ok": sum(1 for r in results if r.get("ok")),
            "issues": sum(1 for r in results if not r.get("ok")),
            "unsafe_files": sum(
                1
                for r in results
                for m in r.get("memory", [])
                if not m.get("safe", True)
            ),
        },
    }
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Scan projects under a parent directory for memory.json safety (no symlink/outside/hardlink)."
    )
    ap.add_argument("paths", nargs="+", help="Parent directories to scan")
    ap.add_argument(
        "--report",
        help="Optional path to write aggregated JSON report (stdout always prints)",
    )
    args = ap.parse_args()
    full: Dict[str, Any] = {"reports": []}
    for p in args.paths:
        rep = scan_parent(Path(p))
        full["reports"].append(rep)
    txt = json.dumps(full, ensure_ascii=False, indent=2)
    print(txt)
    if args.report:
        try:
            Path(args.report).expanduser().resolve().write_text(txt, encoding="utf-8")
        except Exception:
            pass


if __name__ == "__main__":
    main()
