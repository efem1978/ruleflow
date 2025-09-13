from __future__ import annotations

from pathlib import Path

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_ci_validate_license_exception_path(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # 强制启用发布许可门禁
    srv.cfg = {"license": {"required": True}}
    # 提供一个项目级 license.json，但内容为非法 JSON，以触发 _verify_license 异常
    lic = tmp_path / ".mcp" / "license.json"
    lic.parent.mkdir(parents=True, exist_ok=True)
    lic.write_text("not-json", encoding="utf-8")
    # 由于 license.invalid，ci.validate 应被门禁拒绝（ValueError）
    with pytest.raises(Exception):
        srv._call_tool("ci.validate", {})
