from __future__ import annotations

import subprocess
from pathlib import Path

from mcp_rules_assistant.hooks import install_git_hooks
from mcp_rules_assistant.config import ensure_project_config


def test_install_hooks_generates_docker_gate_and_detects_violations(tmp_path: Path) -> None:
    # fake a git repo dir
    (tmp_path / '.git').mkdir(parents=True, exist_ok=True)
    ensure_project_config(tmp_path / '.mcp/assistant.yaml')
    # compiled rules enable container baseline
    (tmp_path / '.mcp').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.mcp/rules_compiled.json').write_text(
        '{"policy": {"container.policy.baseline": true}}',
        encoding='utf-8'
    )
    out = install_git_hooks(tmp_path)
    docker_gate = tmp_path / '.mcp/dockerfile_gate.py'
    assert docker_gate.exists() and 'Dockerfile' in docker_gate.read_text(encoding='utf-8')
    # write a Dockerfile with baseline violations
    (tmp_path / 'Dockerfile').write_text('FROM alpine:latest\nUSER root\n', encoding='utf-8')
    # run gate script
    p = subprocess.run(['python3', str(docker_gate)], cwd=tmp_path, text=True)
    assert p.returncode != 0

