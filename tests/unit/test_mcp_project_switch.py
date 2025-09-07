from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_project_switch_isolation(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    srv = JsonRpcServer()
    srv.project_root = a
    srv._call_tool("memory.append_turn", {"role": "user", "content": "在A"})
    snap_a = srv._call_tool("memory.snapshot", {})
    assert any("在A" in t.get("content", "") for t in snap_a.get("turns", []))
    # switch
    srv._call_tool("project.switch", {"path": str(b)})
    srv._call_tool("memory.append_turn", {"role": "user", "content": "在B"})
    snap_b = srv._call_tool("memory.snapshot", {})
    assert any("在B" in t.get("content", "") for t in snap_b.get("turns", []))
    assert not any("在A" in t.get("content", "") for t in snap_b.get("turns", []))
