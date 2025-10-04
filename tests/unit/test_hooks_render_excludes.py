from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.hooks import generate_pre_commit_config


def test_no_skip_xfail_hook_excludes_tests(tmp_path: Path) -> None:
    p = generate_pre_commit_config(tmp_path)
    text = p.read_text(encoding="utf-8")
    assert ":(exclude)tests/*" in text or " mcp_rules_assistant" in text
