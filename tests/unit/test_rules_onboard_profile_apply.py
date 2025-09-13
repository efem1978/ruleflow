from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _read_yaml_text(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def test_rules_onboard_profile_and_apply(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path

    # preview (no apply): expect profile & summary present
    out = srv._call_tool(
        "rules.onboard",
        {
            "scenario": "enterprise",
            "complexity": "large",
            "devMode": "tdd",
            "apply": False,
        },
    )
    assert out.get("ok") is True
    prof = out.get("profile") or {}
    assert (
        isinstance(prof, dict)
        and "coverage" in prof
        and "security" in prof
        and "license" in prof
    )
    assert isinstance(out.get("summary", ""), str) and out["summary"].strip() != ""
    assert out.get("applied") is False

    # apply and verify assistant.yaml written with key toggles
    out2 = srv._call_tool(
        "rules.onboard",
        {
            "scenario": "enterprise",
            "complexity": "large",
            "devMode": "tdd",
            "apply": True,
        },
    )
    assert out2.get("ok") is True and out2.get("applied") is True
    cfg = tmp_path / ".mcp/assistant.yaml"
    txt = _read_yaml_text(cfg)
    # license required should be enabled for enterprise
    assert "license:" in txt and "required: true" in txt
    # coverage.min_module should reflect thresholds recommended
    assert "coverage:" in txt and "min_module:" in txt
    # CI toggles should be present for enterprise+large (strict/security)
    assert "ci:" in txt and ("hadolint: true" in txt or "semgrep_config:" in txt)
