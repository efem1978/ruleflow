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
        "    <class filename=\"near.py\" line-rate=\"0.905\"/>\n"
        "    <class filename=\"far.py\" line-rate=\"0.80\"/>\n"
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    path.write_text(text, encoding="utf-8")


def test_tool_coverage_near_uses_config_defaults(tmp_path: Path) -> None:
    _write_cov_xml(tmp_path / "coverage.xml")
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    # Set threshold 0.90; set near defaults to within 5%, top 1
    cfg.write_text(
        "performance:\n  on_push:\n    coverage: {min_module: 0.90}\ncoverage:\n  near: {within: 0.05, top: 1}\n",
        encoding="utf-8",
    )
    r = srv.handle(_req("tools/call", {"name": "coverage.near", "arguments": {}}))
    data = r.get("result", {})
    assert data.get("ok") is True
    items = data.get("near") or []
    # Only 'near.py' should be included due to top=1 and within=5%
    assert any((it.get("file") == "near.py") for it in items)
    assert all((it.get("file") != "far.py") for it in items)
    assert len(items) == 1

