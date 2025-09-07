from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_mcp_ide_scaffold_vscode(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool("ide.scaffold", {"editor": "vscode"})
    assert out.get("ok") is True
    for rel in out.get("files", []):
        assert (tmp_path / rel).exists()


def test_mcp_compliance_commitment_write(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool("compliance.commitment", {"write": True})
    assert out.get("ok") is True
    p = tmp_path / ".mcp/compliance.md"
    assert p.exists()
    assert "AI 合规承诺" in p.read_text(encoding="utf-8")
