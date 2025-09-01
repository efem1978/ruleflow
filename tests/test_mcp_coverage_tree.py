from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def _write_cov_xml(path: Path) -> None:
    text = (
        "<coverage>\n"
        "  <packages><package><classes>\n"
        "    <class filename=\"pkg/a/core.py\" line-rate=\"0.80\" lines-valid=\"10\" lines-covered=\"8\"/>\n"
        "    <class filename=\"pkg/b/mod.py\" line-rate=\"0.85\" lines-valid=\"20\" lines-covered=\"17\"/>\n"
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    path.write_text(text, encoding="utf-8")


def test_coverage_tree_resource(tmp_path: Path) -> None:
    _write_cov_xml(tmp_path / "coverage.xml")
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    rlist = srv.handle(_req("resources/list"))
    tree_uri = next(r.get("uri") for r in rlist.get("result", {}).get("resources", []) if str(r.get("uri")).endswith("/tree"))
    resp = srv.handle(_req("resources/read", {"uri": tree_uri}))
    data = json.loads(resp.get("result", {}).get("text") or "{}")
    assert data.get("ok") is True
    tree = data.get("tree") or {}
    assert isinstance(tree, dict) and tree.get("children")
