#!/usr/bin/env python3
"""
Batch hard-disable memory writes for projects and optionally verify.

Usage:
  python scripts/harden_projects.py --verify <proj1> <proj2> ...
  python scripts/harden_projects.py --auto --root "$HOME/Desktop/人工智能编程" --verify

Effects per project directory:
  - Ensures .mcp/assistant.yaml exists
  - Sets memory.hard_disable: true, memory.allow_write: false
  - Sets project.allow_switch: false
  - When --verify, launches an in-process server bound to the project and attempts
    a memory.append_turn, which should be denied; writes .mcp/dashboard/security_verify.json
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List

import yaml


def edit_config(proj: Path) -> Path:
    proj = proj.resolve()
    mcp = proj / ".mcp"
    mcp.mkdir(parents=True, exist_ok=True)
    cfg_p = mcp / "assistant.yaml"
    data: Dict[str, object] = {}
    if cfg_p.exists():
        try:
            data = yaml.safe_load(cfg_p.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
    mem = data.get("memory") if isinstance(data.get("memory"), dict) else {}
    if not isinstance(mem, dict):
        mem = {}
    mem["hard_disable"] = True
    mem["allow_write"] = False
    data["memory"] = mem
    proj_cfg = data.get("project") if isinstance(data.get("project"), dict) else {}
    if not isinstance(proj_cfg, dict):
        proj_cfg = {}
    proj_cfg["allow_switch"] = False
    data["project"] = proj_cfg
    cfg_p.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return cfg_p


def verify(proj: Path) -> Dict[str, object]:
    proj = proj.resolve()
    from mcp_rules_assistant.mcp_server import JsonRpcServer

    os.environ["MCP_STRICT_ISOLATION"] = "1"
    os.environ["MCP_PROJECT_ROOT"] = str(proj)
    srv = JsonRpcServer()
    try:
        out = srv._call_tool(
            "memory.append_turn",
            {"role": "assistant", "content": "SEC_VERIFY", "meta": {"src": "verify"}},
        )
    except Exception as e:
        out = {"exc": str(e)}
    ok = isinstance(out, dict) and out.get("ok") is False
    dash = proj / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    log = {"project": str(proj), "result": out}
    (dash / "security_verify.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"project": str(proj), "denied": ok, "raw": out}


def discover(root: Path) -> List[Path]:
    root = root.resolve()
    out: List[Path] = []
    for p in root.iterdir():
        try:
            if not p.is_dir():
                continue
            if (p / ".mcp").exists() or (p / ".git").exists():
                out.append(p)
        except Exception:
            continue
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("projects", nargs="*", help="project paths")
    ap.add_argument("--verify", action="store_true", help="verify append is denied")
    ap.add_argument("--auto", action="store_true", help="auto discover under --root")
    ap.add_argument("--root", default=str(Path.home()), help="root to auto discover")
    args = ap.parse_args()
    targets: List[Path] = []
    if args.auto:
        targets.extend(discover(Path(args.root)))
    targets.extend(Path(p).expanduser().resolve() for p in args.projects)
    # de-dup
    uniq: List[Path] = []
    seen = set()
    for t in targets:
        if str(t) in seen:
            continue
        seen.add(str(t))
        uniq.append(t)
    results = []
    for t in uniq:
        try:
            edit_config(t)
            if args.verify:
                results.append(verify(t))
        except Exception as e:
            results.append({"project": str(t), "error": str(e)})
    print(json.dumps({"hardened": [str(p) for p in uniq], "verify": results}, ensure_ascii=False))


if __name__ == "__main__":
    main()

