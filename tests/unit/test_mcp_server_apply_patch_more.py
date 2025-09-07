from __future__ import annotations

import os
from pathlib import Path

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_fs_apply_patch_max_bytes_default_fallback(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # Inject bad execution.max_content_bytes to hit except path
    srv.cfg.setdefault("execution", {})
    srv.cfg["execution"]["max_content_bytes"] = {"oops": True}  # int() will fail
    out = srv._call_tool(
        "fs.apply_patch",
        {"files": [{"path": "ok.txt", "content": "hi"}]},
    )
    assert out.get("ok") is True
