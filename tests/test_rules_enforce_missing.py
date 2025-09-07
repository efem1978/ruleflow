from __future__ import annotations

from pathlib import Path

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_rules_enforce_requires_compiled_rules(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    with pytest.raises(Exception) as e:
        srv._call_tool("rules.enforce", {})
    assert "compiled rules not found" in str(e.value)
