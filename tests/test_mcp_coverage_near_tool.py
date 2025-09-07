from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def _write_cov_xml(path: Path) -> None:
    path.write_text(
        '<coverage><packages><package><classes>\n<class filename="a.py" line-rate="0.905"/>\n</classes></package></packages></coverage>\n',
        encoding="utf-8",
    )


def test_tools_call_coverage_near(tmp_path: Path) -> None:
    _write_cov_xml(tmp_path / "coverage.xml")
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # set threshold to 0.90
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        "performance:\n  on_push:\n    coverage: {min_module: 0.90}\n", encoding="utf-8"
    )
    r = srv.handle(
        _req(
            "tools/call",
            {"name": "coverage.near", "arguments": {"within": 0.03, "top": 10}},
        )
    )
    data = r.get("result", {})
    assert data.get("ok") is True
    assert any((it.get("file") == "a.py") for it in (data.get("near") or []))
