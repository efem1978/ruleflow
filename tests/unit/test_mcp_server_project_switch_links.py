from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer
from mcp_rules_assistant.memory import MemoryManager


def test_project_switch_records_links(tmp_path: Path) -> None:
    proj1 = tmp_path / "proj1"
    proj2 = tmp_path / "proj2"
    proj1.mkdir()
    proj2.mkdir()

    srv = JsonRpcServer()
    srv.project_root = proj1
    # Ensure server memory manager is bound to proj1 before switching
    srv.mm = MemoryManager(proj1)

    # Switch to proj2
    out = srv._call_tool("project.switch", {"path": str(proj2)})
    assert out.get("ok") is True

    # Old project memory should record switched_to
    mem1 = proj1 / ".mcp" / "memory.json"
    assert mem1.exists()
    d1 = json.loads(mem1.read_text(encoding="utf-8"))
    links1 = d1.get("links") or []
    assert any(link.get("task") == "switched_to" for link in links1)

    # New project memory should record switched_from
    mem2 = proj2 / ".mcp" / "memory.json"
    assert mem2.exists()
    d2 = json.loads(mem2.read_text(encoding="utf-8"))
    links2 = d2.get("links") or []
    assert any(link.get("task") == "switched_from" for link in links2)
