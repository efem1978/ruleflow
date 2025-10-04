from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import hooks


def test_install_git_hooks_ignores_invalid_compiled(tmp_path: Path) -> None:
    d = tmp_path / ".mcp"
    d.mkdir(parents=True, exist_ok=True)
    (d / "rules_compiled.json").write_text("{invalid", encoding="utf-8")
    out = hooks.install_git_hooks(tmp_path)
    # no dockerfile_gate when compiled policy parsing fails
    assert "dockerfile_gate" not in out


def test_render_ci_yaml_with_invalid_compiled(tmp_path: Path) -> None:
    d = tmp_path / ".mcp"
    d.mkdir(parents=True, exist_ok=True)
    (d / "rules_compiled.json").write_text("{invalid", encoding="utf-8")
    y = hooks.render_github_ci_yaml(tmp_path)
    # Should not include steps gated by compiled policy
    assert "Pre-commit (all files)" not in y
    assert "Check Dockerfile existence" not in y
