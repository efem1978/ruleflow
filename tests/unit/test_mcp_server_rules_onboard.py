from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_mcp_rules_onboard_dry_run(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool("rules.onboard", {"apply": False})
    assert out.get("ok") is True
    assert "thresholds" in out
    # no file written in dry-run
    assert not (tmp_path / ".mcp/assistant.yaml").exists()


def test_mcp_rules_onboard_apply_writes(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool(
        "rules.onboard",
        {"scenario": "pro", "complexity": "medium", "devMode": "tdd", "apply": True},
    )
    assert out.get("ok") is True
    cfg = tmp_path / ".mcp/assistant.yaml"
    assert cfg.exists()
    text = cfg.read_text(encoding="utf-8")
    # pro+medium → min_module=0.92, mutation_test false
    assert "min_module: 0.92" in text
    assert "mutation_test: false" in text


def test_mcp_rules_onboard_apply_enterprise(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool(
        "rules.onboard",
        {
            "scenario": "enterprise",
            "complexity": "large",
            "devMode": "tdd",
            "apply": True,
        },
    )
    assert out.get("ok") is True
    cfg = tmp_path / ".mcp/assistant.yaml"
    assert cfg.exists()
    text = cfg.read_text(encoding="utf-8")
    # enterprise+large → min_module=0.95, mutation_test true
    assert "min_module: 0.95" in text
    assert "mutation_test: true" in text
