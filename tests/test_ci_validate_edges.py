from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_ci_validate_reports_missing_steps_when_no_ci(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    r = srv.handle(_req("tools/call", {"name": "ci.validate"}))
    checks = r.get("result", {}).get("checks", {})
    assert checks.get("exists") is False
    assert checks.get("has_precommit") is False
    assert checks.get("has_hadolint") is False
    assert checks.get("has_semgrep") is False
    assert checks.get("has_tests") is False
    assert checks.get("has_bandit") is False


def test_ci_validate_detects_precommit_only(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    ci = tmp_path / ".github/workflows/ci.yml"
    ci.parent.mkdir(parents=True, exist_ok=True)
    ci.write_text(
        """
name: CI
jobs:
  build:
    steps:
      - name: Pre-commit (all files)
        run: |
          pre-commit run --all-files
""".lstrip(),
        encoding="utf-8",
    )
    r = srv.handle(_req("tools/call", {"name": "ci.validate"}))
    checks = r.get("result", {}).get("checks", {})
    assert checks.get("exists") is True
    assert checks.get("has_precommit") is True
    assert checks.get("has_hadolint") is False
    assert checks.get("has_semgrep") is False
    assert checks.get("has_tests") is False
    assert checks.get("has_bandit") is False
