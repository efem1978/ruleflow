from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_rules_maxima_resource_missing_and_invalid(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    rlist = srv.handle(_req("resources/list"))
    max_uri = next(
        r["uri"]
        for r in rlist["result"]["resources"]
        if str(r["uri"]).endswith("/maxima")
    )
    # missing compiled.json → expect error in response
    err = srv.handle(_req("resources/read", {"uri": max_uri}))
    assert "error" in err and "rules resource not found" in err["error"]["message"]
    # invalid compiled.json → maxima should return empty dict JSON
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/rules_compiled.json").write_text("{invalid", encoding="utf-8")
    ok = srv.handle(_req("resources/read", {"uri": max_uri}))
    assert ok.get("result", {}).get("mimeType") == "application/json"
    data = json.loads(ok.get("result", {}).get("text") or "{}")
    assert isinstance(data.get("maxima"), dict)
