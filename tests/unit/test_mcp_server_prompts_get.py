from __future__ import annotations

import os
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_prompts_list_and_get(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("MCP_PROMPTS_ENABLE", "1")  # enable prompts
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # list
    res = srv.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "prompts/list", "params": {}}
    )
    prompts = (res.get("result", {}) or {}).get("prompts", [])
    assert isinstance(prompts, list)
    # get
    res2 = srv.handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "prompts/get",
            "params": {"name": "handoff.next_steps"},
        }
    )
    assert (res2.get("result", {}) or {}).get("ok") is True
