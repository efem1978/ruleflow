from __future__ import annotations

import os

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id_: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}


def test_prompts_enabled_via_env(monkeypatch) -> None:
    monkeypatch.setenv("MCP_PROMPTS_ENABLE", "1")
    srv = JsonRpcServer()
    rlist = srv.handle(_req("prompts/list"))
    prompts = rlist.get("result", {}).get("prompts") or []
    assert isinstance(prompts, list) and len(prompts) >= 2
    rget = srv.handle(_req("prompts/get", {"name": "handoff.next_steps"}))
    assert rget.get("result", {}).get("ok") is True
    tpl = rget.get("result", {})
    assert tpl.get("name") == "handoff.next_steps" and isinstance(
        tpl.get("messages"), list
    )
