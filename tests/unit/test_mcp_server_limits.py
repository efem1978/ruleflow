from __future__ import annotations

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id_: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}


def test_request_too_large(monkeypatch) -> None:
    srv = JsonRpcServer()
    srv.cfg.setdefault("execution", {})["max_request_bytes"] = 10
    big = {"x": "a" * 100}
    res = srv.handle(_req("ping", big))
    err = res.get("error", {})
    assert err and "too large" in err.get("message", "")


def test_rate_limit_exceeded() -> None:
    srv = JsonRpcServer()
    srv.cfg.setdefault("execution", {})["rate_limit_rps"] = 0
    _ = srv.handle(_req("ping"))
    res = srv.handle(_req("ping"))
    err = res.get("error", {})
    assert err and "rate limit" in err.get("message", "")


def test_non_serializable_params_and_bad_max_bytes() -> None:
    srv = JsonRpcServer()
    ex = srv.cfg.setdefault("execution", {})
    ex["max_request_bytes"] = "bad-int"  # force int() to raise -> use default
    # params contain a non-serializable object to hit sz exception branch
    res = srv.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {"bad": object()}},
    )
    assert res.get("result", {}).get("ok") is True
