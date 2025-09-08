import os
from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None) -> dict:
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}


def test_prompts_enabled_via_env_returns_templates(monkeypatch) -> None:
    monkeypatch.setenv("MCP_PROMPTS_ENABLE", "1")
    srv = JsonRpcServer()

    rlist = srv.handle(_req("prompts/list"))
    prompts = rlist.get("result", {}).get("prompts", [])
    names = {p.get("name") for p in prompts}
    assert "handoff.next_steps" in names and "rules.summary" in names

    rget = srv.handle(_req("prompts/get", {"name": "handoff.next_steps"}))
    tpl = rget.get("result", {})
    assert tpl.get("ok") is True
    assert tpl.get("name") == "handoff.next_steps"

