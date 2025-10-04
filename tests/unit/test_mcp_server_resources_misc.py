from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id_: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}


def test_resources_read_config_and_ci(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # config
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/assistant.yaml").write_text(
        "language: python\n", encoding="utf-8",
    )
    r1 = srv.handle(
        _req("resources/read", {"uri": f"config://project/{'x'}/assistant.yaml"}),
    )
    assert r1.get("result", {}).get("mimeType") == "text/yaml"
    # ci
    (tmp_path / ".github/workflows").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".github/workflows/ci.yml").write_text("name: CI\n", encoding="utf-8")
    r2 = srv.handle(_req("resources/read", {"uri": f"ci://project/{'x'}/workflow"}))
    assert r2.get("result", {}).get("mimeType") == "text/yaml"


def test_tool_rules_maxima(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/rules_compiled.json").write_text(
        '{"meta": {"maxima": {"coverage.max_core": 0.99}}}', encoding="utf-8",
    )
    r = srv.handle(_req("tools/call", {"name": "rules.maxima", "arguments": {}}))
    assert r.get("result", {}).get("ok") is True
