from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.config import ensure_project_config
from mcp_rules_assistant.hooks import generate_pre_commit_config


def test_precommit_blocks_with_secrets_and_docker_baseline(tmp_path: Path) -> None:
    ensure_project_config(tmp_path / ".mcp/assistant.yaml")
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    # enable secrets scan and docker baseline via compiled rules
    (tmp_path / ".mcp/rules_compiled.json").write_text(
        '{"policy": {"security.secrets_scan": true, "container.policy.baseline": true}}',
        encoding="utf-8",
    )
    pcfg = generate_pre_commit_config(tmp_path)
    text = pcfg.read_text(encoding="utf-8")
    # detect-secrets block (push stage)
    assert "detect-secrets" in text and "stages: [push]" in text
    # dockerfile baseline local hook present
    assert (
        "dockerfile-baseline" in text
        and "entry: python .mcp/dockerfile_gate.py" in text
    )
    # cov-fail-under reflects min_module from config (default 0.90 => 90)
    assert "--cov-fail-under=90" in text
