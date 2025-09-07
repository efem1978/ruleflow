from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import hooks
from mcp_rules_assistant.config import ensure_project_config


def test_render_github_ci_with_mutation_and_vscode_required(tmp_path: Path) -> None:
    ensure_project_config(tmp_path / ".mcp/assistant.yaml")
    # write compiled rules to enable sast_strict and container baseline
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/rules_compiled.json").write_text(
        '{"policy": {"security.sast_strict": true, "container.policy.baseline": true}}',
        encoding="utf-8",
    )
    # update project config to force mutation and vscode job requirement
    p = tmp_path / ".mcp/assistant.yaml"
    text = p.read_text(encoding="utf-8")
    text += "\nperformance:\n  on_push:\n    mutation_test: true\nci:\n  vscode_required: true\n"
    p.write_text(text, encoding="utf-8")
    y = hooks.render_github_ci_yaml(tmp_path)
    assert "Mutation testing" in y and "VS Code extension tests" in y
