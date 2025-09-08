from __future__ import annotations

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None) -> dict:
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}


def test_memory_links_resource_list_and_read(tmp_path):
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # add a cross-project link then read via resources/read .../links
    srv.mm.add_link("projX", "sync", "relates")
    rlist = srv.handle(_req("resources/list"))
    lst = rlist.get("result", {}).get("resources", [])
    assert any(str(x.get("uri", "")).endswith("/links") for x in lst)
    # Now read links resource
    pid = srv._project_id()
    r = srv.handle(_req("resources/read", {"uri": f"memory://{pid}/links"}))
    assert r.get("result", {}).get("mimeType") == "application/json"
    txt = r.get("result", {}).get("text", "{}")
    assert "links" in txt and "projX" in txt
