from __future__ import annotations

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_mcp_prompts_minimal_endpoints() -> None:
    srv = JsonRpcServer()
    rlist = srv.handle(_req("prompts/list"))
    assert rlist.get("result", {}).get("prompts") == []
    rget = srv.handle(_req("prompts/get", {"name": "unknown"}))
    assert rget.get("result", {}).get("ok") is False
