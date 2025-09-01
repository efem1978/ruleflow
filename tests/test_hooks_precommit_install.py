from __future__ import annotations

from pathlib import Path
import types

from mcp_rules_assistant import hooks


def test_install_git_hooks_with_precommit(monkeypatch, tmp_path: Path) -> None:
    # Pretend pre-commit exists and intercept subprocess.run calls
    calls = []
    monkeypatch.setattr('mcp_rules_assistant.hooks.shutil.which', lambda name: '/usr/bin/pre-commit')

    def fake_run(cmd, cwd=None, check=False):
        calls.append((tuple(cmd), bool(cwd), bool(check)))
        class P: pass
        return P()

    monkeypatch.setattr('mcp_rules_assistant.hooks.subprocess.run', fake_run)
    out = hooks.install_git_hooks(tmp_path)
    assert out.get('pre_commit_config')
    # ensure pre-commit installs attempted
    assert any('pre-commit' in c[0][0] for c in calls)

