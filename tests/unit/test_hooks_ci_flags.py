from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.hooks import render_github_ci_yaml
from mcp_rules_assistant.config import ensure_project_config


def test_ci_yaml_contains_precommit_and_hadolint_when_enabled(tmp_path: Path) -> None:
    # base project config
    ensure_project_config(tmp_path / '.mcp/assistant.yaml')
    # enable hadolint in ci
    p = tmp_path / '.mcp/assistant.yaml'
    txt = p.read_text(encoding='utf-8')
    txt += '\nci:\n  hadolint: true\n'
    p.write_text(txt, encoding='utf-8')
    # compiled rules gate secrets + container.required to trigger steps
    (tmp_path / '.mcp').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.mcp/rules_compiled.json').write_text(
        '{"policy": {"security.secrets_scan": true, "container.required": true}}',
        encoding='utf-8'
    )
    y = render_github_ci_yaml(tmp_path)
    # pre-commit scan step exists
    assert 'Pre-commit (all files)' in y
    # hadolint step exists when hadolint enabled and container.required present
    assert 'Dockerfile Lint (hadolint)' in y

