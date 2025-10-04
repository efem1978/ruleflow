from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_coverage_summary_resource_missing(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    rlist = srv.handle(_req("resources/list"))
    cov_uri = next(
        r.get("uri")
        for r in rlist.get("result", {}).get("resources", [])
        if str(r.get("uri")).endswith("/summary")
    )
    rcov = srv.handle(_req("resources/read", {"uri": cov_uri}))
    data = json.loads(rcov.get("result", {}).get("text") or "{}")
    assert data.get("ok") is False
