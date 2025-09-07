from __future__ import annotations

import os
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_apply_patch_write_only(tmp_path: Path) -> None:
    old = os.getcwd()
    os.chdir(tmp_path)
    try:
        srv = JsonRpcServer()
        res = srv._call_tool(
            "fs.apply_patch",
            {
                "files": [{"path": "foo.py", "content": "def add(a,b): return a+b\n"}],
                "runChecks": False,
                "strict": False,
            },
        )
        assert res.get("ok") is True and int(res.get("written", 0)) == 1
        assert (tmp_path / "foo.py").exists()
        # checks 字段存在且 ok（未运行实际检查）
        assert (res.get("checks") or {}).get("ok") is True
    finally:
        os.chdir(old)


def test_apply_patch_strict_with_checks(tmp_path: Path) -> None:
    old = os.getcwd()
    os.chdir(tmp_path)
    try:
        srv = JsonRpcServer()
        res = srv._call_tool(
            "fs.apply_patch",
            {
                "files": [{"path": "foo.py", "content": "def add(a,b): return a+b\n"}],
                "runChecks": True,
                "strict": True,
            },
        )
        assert res.get("ok") is True
        checks = res.get("checks") or {}
        assert checks.get("ok") is True
    finally:
        os.chdir(old)
