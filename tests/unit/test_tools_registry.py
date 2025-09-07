from __future__ import annotations

from mcp_rules_assistant.tools import Tool, registry, setup_default_tools


def test_register_and_list_tools(monkeypatch) -> None:
    # isolate registry by resetting internal dict
    setup_default_tools()
    names = {t.name for t in registry.list()}
    assert "project.detect" in names and "ci.generate" in names
    # register custom
    registry.register(Tool("custom.tool", "x"))
    assert any(t.name == "custom.tool" for t in registry.list())
