from __future__ import annotations

import json
import os
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_memory_hard_disable_env_overrides_allow_write(
    tmp_path: Path, monkeypatch
) -> None:
    # enable allow_write in project config
    mcp = tmp_path / ".mcp"
    mcp.mkdir(parents=True, exist_ok=True)
    (mcp / "assistant.yaml").write_text(
        "memory:\n  allow_write: true\n", encoding="utf-8"
    )
    # strict isolation + global hard disable
    monkeypatch.setenv("MCP_STRICT_ISOLATION", "1")
    monkeypatch.setenv("MCP_MEMORY_HARD_DISABLE", "1")
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))

    # ensure test bypass doesn't auto-allow writes
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    srv = JsonRpcServer()
    out = srv.handle(
        _req(
            "tools/call",
            {
                "name": "memory.append_turn",
                "arguments": {"role": "assistant", "content": "x"},
            },
        )
    )
    res = out.get("result") or {}
    assert res.get("ok") is False
    assert res.get("error") == "memory_write_disabled"
    # audit trail should have at least one entry
    audit = tmp_path / ".mcp" / "dashboard" / "security_audit.jsonl"
    assert audit.exists(), "security audit log should exist"
    lines = audit.read_text(encoding="utf-8").splitlines()
    assert any(
        "memory.write_denied" in ln or "memory.append_denied" in ln for ln in lines
    )


def test_project_switch_denied_audit(tmp_path: Path, monkeypatch) -> None:
    # strict isolation disallows project.switch by default
    mcp = tmp_path / ".mcp"
    mcp.mkdir(parents=True, exist_ok=True)
    (mcp / "assistant.yaml").write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("MCP_STRICT_ISOLATION", "1")
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))
    srv = JsonRpcServer()
    # switching to another temp dir should be denied and audited
    other = tmp_path / "other"
    other.mkdir()
    try:
        srv._call_tool("project.switch", {"path": str(other)})
    except Exception:
        pass
    audit = tmp_path / ".mcp" / "dashboard" / "security_audit.jsonl"
    assert audit.exists(), "security audit log should exist"
    content = audit.read_text(encoding="utf-8")
    assert "project.switch_denied" in content
