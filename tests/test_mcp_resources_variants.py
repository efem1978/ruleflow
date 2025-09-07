from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_resources_read_config_progress_and_ci(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # ensure config exists and write a plan
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/assistant.yaml").write_text(
        "performance:\n  on_push:\n    coverage: {min_module: 0.90}\n", encoding="utf-8"
    )
    (tmp_path / ".mcp/plan.md").write_text(
        "# 计划\n- 状态: planned\n", encoding="utf-8"
    )
    # generate ci
    from mcp_rules_assistant.hooks import generate_github_ci

    generate_github_ci(tmp_path)
    # list
    rlist = srv.handle(_req("resources/list"))
    uris = [r.get("uri") for r in rlist.get("result", {}).get("resources", [])]
    cfg_uri = next(u for u in uris if str(u).startswith("config://"))
    plan_uri = next(u for u in uris if str(u).startswith("progress://"))
    ci_uri = next(u for u in uris if str(u).startswith("ci://"))
    rcfg = srv.handle(_req("resources/read", {"uri": cfg_uri}))
    assert rcfg.get("result", {}).get("mimeType") == "text/yaml"
    rplan = srv.handle(_req("resources/read", {"uri": plan_uri}))
    assert rplan.get("result", {}).get("mimeType") == "text/markdown"
    rci = srv.handle(_req("resources/read", {"uri": ci_uri}))
    assert rci.get("result", {}).get("mimeType") == "text/yaml"
