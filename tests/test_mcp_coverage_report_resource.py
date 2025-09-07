from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def _write_cov_xml(path: Path) -> None:
    path.write_text(
        "<coverage>\n  <packages><package><classes>\n"
        '<class filename="a.py" line-rate="0.905"/>\n'
        '<class filename="b.py" line-rate="0.880"/>\n'
        "</classes></package></packages>\n</coverage>\n",
        encoding="utf-8",
    )


def test_mcp_coverage_report_resource(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # write config min_module 0.90
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/assistant.yaml").write_text(
        "performance:\n  on_push:\n    coverage: {min_module: 0.90}\n", encoding="utf-8"
    )
    _write_cov_xml(tmp_path / "coverage.xml")
    rlist = srv.handle(_req("resources/list"))
    uris = [r.get("uri") for r in rlist.get("result", {}).get("resources", [])]
    rep_uri = next(u for u in uris if str(u).endswith("/report"))
    r = srv.handle(_req("resources/read", {"uri": rep_uri}))
    data = json.loads(r.get("result", {}).get("text") or "{}")
    assert data.get("ok") is True
    assert (
        isinstance(data.get("weak"), list)
        and isinstance(data.get("groups"), list)
        and isinstance(data.get("near"), list)
    )
