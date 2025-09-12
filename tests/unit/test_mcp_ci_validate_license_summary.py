from __future__ import annotations

from pathlib import Path

import yaml

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_ci_validate_writes_summary_when_license_required(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    # enable license.required
    (tmp_path / ".mcp/assistant.yaml").write_text(
        yaml.safe_dump(
            {"license": {"required": True}}, sort_keys=False, allow_unicode=True
        ),
        encoding="utf-8",
    )
    try:
        srv._call_tool("ci.validate", {})
        assert False, "expected license gate error"
    except Exception:
        pass
    rc = tmp_path / ".mcp" / "dashboard" / "release_check.md"
    assert rc.exists()
    txt = rc.read_text(encoding="utf-8")
    assert "License required" in txt
