from __future__ import annotations

from pathlib import Path

import yaml

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_config_update_license_gate(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # write assistant.yaml with license.required=true
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    cfg = {
        "license": {"required": True},
        "ci": {},
    }
    (tmp_path / ".mcp/assistant.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    # touching a CI key should trigger license check and raise (since no license file activated)
    try:
        srv._call_tool("config.update", {"data": {"vscode_required": True}})
        assert False, "expected license gate error"
    except Exception as e:
        assert "license" in str(e).lower()
