from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_config_update_fs_guard_flags(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool(
        "config.update",
        {"execution": {"fs_guard_post_checks": True, "fs_guard_strict": True}},
    )
    assert out.get("ok") is True
    res = srv._call_tool("config.get", {})
    cfg = res.get("config", {})
    ex = cfg.get("execution", {}) or {}
    assert ex.get("fs_guard_post_checks") is True
    assert ex.get("fs_guard_strict") is True
