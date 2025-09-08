from __future__ import annotations

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_nl_command_returns_none_tool_when_unmapped(tmp_path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool("nl.command", {"text": "this does not map"})
    parsed = out.get("parsed", {})
    assert parsed.get("tool") is None
