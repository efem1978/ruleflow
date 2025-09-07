from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_ci_validate_has_node_tests_flag(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # Without extension workspace, generate CI and validate → has_node_tests likely False
    g1 = srv.handle(_req("tools/call", {"name": "ci.generate"}))
    assert (tmp_path / ".github/workflows/ci.yml").exists()
    v1 = srv.handle(_req("tools/call", {"name": "ci.validate"}))
    checks1 = v1.get("result", {}).get("checks", {})
    assert checks1.get("has_node_tests") is False

    # Create extensions/vscode/package.json to enable Node job in CI template
    extpkg = tmp_path / "extensions/vscode/package.json"
    extpkg.parent.mkdir(parents=True, exist_ok=True)
    extpkg.write_text('{"name":"ext","version":"0.0.1"}', encoding="utf-8")
    g2 = srv.handle(_req("tools/call", {"name": "ci.generate"}))
    v2 = srv.handle(_req("tools/call", {"name": "ci.validate"}))
    checks2 = v2.get("result", {}).get("checks", {})
    assert checks2.get("has_node_tests") is True
