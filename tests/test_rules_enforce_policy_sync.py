from __future__ import annotations

from pathlib import Path

import yaml

from mcp_rules_assistant.config import ensure_project_config
from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_rules_enforce_syncs_ci_and_returns_enforced(tmp_path: Path) -> None:
    ensure_project_config(tmp_path / ".mcp/assistant.yaml")
    compiled_dir = tmp_path / ".mcp"
    compiled_dir.mkdir(parents=True, exist_ok=True)
    (compiled_dir / "rules_compiled.json").write_text(
        (
            '{"policy": {"coverage.min_module": 0.91, "test.warnings_as_errors": true,'
            ' "security.secrets_scan": true, "security.sast_strict": true,'
            ' "container.required": true, "container.policy.baseline": true}}'
        ),
        encoding="utf-8",
    )
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool("rules.enforce", {})
    assert out.get("ok") is True
    enforced = out.get("enforced") or []
    # coverage + key gates
    assert any(str(s).startswith("coverage.min_module=") for s in enforced)
    assert "warnings_as_errors" in enforced
    assert "secrets_scan" in enforced
    assert "sast_strict" in enforced
    assert "container_required" in enforced and "container_baseline" in enforced
    assert (
        any(str(s).startswith("ci.hadolint=") for s in enforced)
        or "ci.hadolint=true" in enforced
    )
    assert any(str(s).startswith("ci.semgrep_config=") for s in enforced)
    # config updated accordingly
    y = (
        yaml.safe_load((tmp_path / ".mcp/assistant.yaml").read_text(encoding="utf-8"))
        or {}
    )
    ci = y.get("ci") or {}
    assert ci.get("hadolint") is True
    assert (ci.get("semgrep_config") or "") != ""
