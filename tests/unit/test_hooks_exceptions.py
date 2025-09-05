from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import hooks


def test_install_hooks_precommit_run_raises(monkeypatch, tmp_path: Path) -> None:
    # simulate pre-commit present and subprocess.run raising -> cover except at 283-284
    (tmp_path / '.git').mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr('mcp_rules_assistant.hooks.shutil.which', lambda name: '/usr/bin/pre-commit')
    class E(Exception): pass
    def bad_run(*a, **k):
        raise E('fail')
    monkeypatch.setattr('mcp_rules_assistant.hooks.subprocess.run', bad_run)
    out = hooks.install_git_hooks(tmp_path)
    assert out.get('pre_commit_config')


def test_install_hooks_commit_template_outer_and_inner_except(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / '.git').mkdir(parents=True, exist_ok=True)
    # outer except: write_text raises
    def bad_write(self, *a, **k):  # noqa: ANN001
        raise OSError('nope')
    from pathlib import Path as P
    gitmsg = tmp_path / '.git/.gitmessage'
    def write_text_proxy(path, text, encoding='utf-8'):
        if path == gitmsg:
            raise OSError('nope')
        return Path.write_text(path, text, encoding=encoding)
    # monkeypatch Path.write_text globally is risky; instead, patch hooks.Path to proxy
    monkeypatch.setattr(hooks, 'Path', Path)
    # inner except: git config raises
    def bad_run(*a, **k):
        raise RuntimeError('git cfg bad')
    monkeypatch.setattr('mcp_rules_assistant.hooks.subprocess.run', bad_run)
    # call
    out = hooks.install_git_hooks(tmp_path)
    # even if exceptions occur, function should return minimal dict
    assert out.get('pre_commit_config') and out.get('pre_push')

