from __future__ import annotations

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_tools_list_contains_new_tools() -> None:
    srv = JsonRpcServer()
    r = srv.handle(_req("tools/list"))
    tools = [t.get("name") for t in r.get("result", {}).get("tools", [])]
    for name in ["coverage.report", "rules.maxima", "env.diagnose"]:
        assert name in tools
