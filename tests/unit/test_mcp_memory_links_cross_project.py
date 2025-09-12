from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_cross_project_links_between_projects(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    srv = JsonRpcServer()
    srv.project_root = a
    # 在项目A记录一个跳转到B的链接
    srv._call_tool(
        "project.link", {"project": "projB", "task": "handoff", "note": "to B"}
    )
    # 切换到B会在B侧记录 switched_from 链接
    srv._call_tool("project.switch", {"path": str(b)})
    # 在B记录一个链接到A
    srv._call_tool(
        "project.link", {"project": "projA", "task": "sync", "note": "from A"}
    )
    # 读取B侧 links 资源
    r = srv.handle(
        _req("resources/read", {"uri": f"memory://{srv._project_id()}/links"})
    )
    txt = (r.get("result", {}) or {}).get("text", "{}")
    import json

    data = json.loads(txt)
    assert isinstance(data.get("links"), list)
    # 至少包含一条链接记录
    assert data["links"], "links should not be empty"
