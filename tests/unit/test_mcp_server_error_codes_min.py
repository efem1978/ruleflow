from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _call(srv: JsonRpcServer, method: str, params: dict) -> dict:
    req = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    return srv.handle(req)


def test_error_code_method_not_found(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    out = _call(srv, "no.such.method", {})
    assert "error" in out and out["error"]["code"] == -32601


def test_error_code_invalid_params_on_unknown_tool(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    out = _call(srv, "tools/call", {"name": "__unknown__", "arguments": {}})
    assert "error" in out and out["error"]["code"] == -32602
