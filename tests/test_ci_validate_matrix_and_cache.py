from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_ci_validate_matrix_and_cache_flags(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    srv.handle(_req("tools/call", {"name": "ci.generate"}))
    v = srv.handle(_req("tools/call", {"name": "ci.validate"}))
    checks = v.get("result", {}).get("checks", {})
    assert checks.get("has_python_matrix") is True
    assert checks.get("has_pip_cache") is True
    assert checks.get("has_artifacts") is True
    assert checks.get("has_junit") is True
    assert checks.get("has_coverage_near") is True
    # Node cache depends on presence of extension package.json in template condition; create to enable
    extpkg = tmp_path / "extensions/vscode/package.json"
    extpkg.parent.mkdir(parents=True, exist_ok=True)
    extpkg.write_text('{"name":"ext","version":"0.0.1"}', encoding="utf-8")
    srv.handle(_req("tools/call", {"name": "ci.generate"}))
    v2 = srv.handle(_req("tools/call", {"name": "ci.validate"}))
    checks2 = v2.get("result", {}).get("checks", {})
    assert checks2.get("has_npm_cache") is True
    # near step 和组合 artifact 路径存在
    assert checks2.get("has_coverage_near") is True
    assert checks2.get("has_near_artifact") is True
    assert checks2.get("has_combined_artifact") is True
    assert checks2.get("has_combined_artifact_zip") is True
