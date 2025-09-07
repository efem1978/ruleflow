from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_ci_workflow_resource_missing_and_present(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    rlist = srv.handle(_req("resources/list"))
    ci_uri = next(
        r["uri"]
        for r in rlist["result"]["resources"]
        if str(r["uri"]).startswith("ci://")
    )
    missing = srv.handle(_req("resources/read", {"uri": ci_uri}))
    assert missing.get("result", {}).get("mimeType") == "text/yaml"
    assert (missing.get("result", {}).get("text") or "") == ""
    # write a workflow and read again
    wf = tmp_path / ".github/workflows/ci.yml"
    wf.parent.mkdir(parents=True, exist_ok=True)
    wf.write_text("name: x\n", encoding="utf-8")
    present = srv.handle(_req("resources/read", {"uri": ci_uri}))
    assert present.get("result", {}).get("mimeType") == "text/yaml"
    assert "name: x" in (present.get("result", {}).get("text") or "")


def test_config_resource_missing_and_present(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    rlist = srv.handle(_req("resources/list"))
    cfg_uri = next(
        r["uri"]
        for r in rlist["result"]["resources"]
        if str(r["uri"]).startswith("config://")
    )
    missing = srv.handle(_req("resources/read", {"uri": cfg_uri}))
    assert missing.get("result", {}).get("mimeType") == "text/yaml"
    assert (missing.get("result", {}).get("text") or "") == ""
    # create config and read again
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        "performance:\n  on_push:\n    coverage: {min_module: 0.90}\n", encoding="utf-8"
    )
    present = srv.handle(_req("resources/read", {"uri": cfg_uri}))
    assert present.get("result", {}).get("mimeType") == "text/yaml"
    assert "coverage:" in (present.get("result", {}).get("text") or "")
