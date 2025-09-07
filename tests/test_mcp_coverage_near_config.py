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
        '    <class filename="weak.py" line-rate="0.905"/>\n'
        '    <class filename="far.py" line-rate="0.80"/>\n'
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    path.write_text(text, encoding="utf-8")


def test_resources_near_uses_config_window_and_top(tmp_path: Path) -> None:
    _write_cov_xml(tmp_path / "coverage.xml")
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # write config: threshold 0.90; near window 5% and top 1
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        (
            "performance:\n  on_push:\n    coverage: {min_module: 0.90}\n"
            "coverage:\n  near: {within: 0.05, top: 1}\n"
        ),
        encoding="utf-8",
    )
    rlist = srv.handle(_req("resources/list"))
    near_uri = next(
        u.get("uri")
        for u in rlist.get("result", {}).get("resources", [])
        if str(u.get("uri")).endswith("/near")
    )
    r = srv.handle(_req("resources/read", {"uri": near_uri}))
    data = json.loads(r.get("result", {}).get("text") or "{}")
    assert data.get("ok") is True
    items = data.get("near") or []
    # within 5%: weak.py (90.5% near 90%) should appear; far.py (80%) should not
    assert any((it.get("file") == "weak.py") for it in items)
    assert all((it.get("file") != "far.py") for it in items)
    # top=1 → only 1 item
    assert len(items) == 1
