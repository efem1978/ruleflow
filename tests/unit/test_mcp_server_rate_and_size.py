from __future__ import annotations

from pathlib import Path

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_request_too_large(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # tighten size limit
    srv.cfg.setdefault("execution", {})["max_request_bytes"] = 1024
    big_args = {"data": "x" * 5000}
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "ping", "arguments": big_args},
    }
    res = srv.handle(req)
    assert (
        isinstance(res, dict)
        and "error" in res
        and "too large" in str(res["error"].get("message", ""))
    )


def test_rate_limit_exceeded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    srv.cfg.setdefault("execution", {})["rate_limit_rps"] = 1
    # Simulate window with one prior call
    srv._rl_window_start = __import__("time").monotonic()
    srv._rl_count = 1
    req = {"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}}
    res = srv.handle(req)
    assert (
        isinstance(res, dict)
        and "error" in res
        and "rate limit" in str(res["error"].get("message", ""))
    )
