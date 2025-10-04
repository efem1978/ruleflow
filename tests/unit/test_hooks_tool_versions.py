from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.hooks import generate_pre_commit_config


def test_pre_commit_tool_versions_from_config(tmp_path: Path) -> None:
    # write assistant.yaml with ci.tool_versions
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        (
            "ci:\n"
            "  tool_versions:\n"
            "    ruff: v0.4.0\n"
            "    black: 24.3.0\n"
            "    isort: 5.12.0\n"
            "    mypy: v1.9.0\n"
            "    bandit: 1.7.5\n"
        ),
        encoding="utf-8",
    )
    p = generate_pre_commit_config(tmp_path)
    t = p.read_text(encoding="utf-8")
    assert "rev: v0.4.0" in t
    assert "rev: 24.3.0" in t
    assert "rev: 5.12.0" in t
    assert "rev: v1.9.0" in t
    assert "rev: 1.7.5" in t
