from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import hooks


def test_render_ci_yaml_includes_vscode_job_when_required(tmp_path: Path) -> None:
    # project config: vscode_required true
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/assistant.yaml").write_text(
        "ci: { vscode_required: true }\n", encoding="utf-8"
    )
    yml = hooks.render_github_ci_yaml(tmp_path)
    assert "vscode:" in yml
    assert "VS Code extension tests" in yml
    # ensure not gated by hashFiles condition
    assert "hashFiles('extensions/vscode/package.json')" not in yml
    # ensure coverage gate present
    assert "Coverage Policy Gate" in yml and "pytest -q" in yml
    # ensure VS Code coverage upload step present
    assert "coverage/lcov.info" in yml
