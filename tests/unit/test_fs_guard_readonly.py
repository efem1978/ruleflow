from __future__ import annotations

from pathlib import Path

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_fs_apply_patch_readonly(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    srv.cfg = {"execution": {"readonly": True}}
    with pytest.raises(Exception):
        srv._call_tool(
            "fs.apply_patch",
            {"files": [{"path": "x.py", "content": "print(1)"}], "runChecks": True},
        )
