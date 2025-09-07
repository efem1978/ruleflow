from __future__ import annotations

from pathlib import Path

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id_: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}


def test_fs_apply_patch_missing_path_and_absolute(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # missing path
    r1 = srv.handle(
        _req(
            "tools/call",
            {
                "name": "fs.apply_patch",
                "arguments": {"files": [{"content": "x"}], "strict": True},
            },
        )
    )
    assert "缺少文件路径" in r1.get("error", {}).get("message", "")
    # absolute path
    r2 = srv.handle(
        _req(
            "tools/call",
            {
                "name": "fs.apply_patch",
                "arguments": {
                    "files": [{"path": str(Path("/etc/hosts")), "content": "x"}]
                },
            },
        )
    )
    assert "绝对路径" in r2.get("error", {}).get("message", "")
