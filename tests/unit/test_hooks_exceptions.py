from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import hooks


def test_install_hooks_precommit_run_raises(monkeypatch, tmp_path: Path) -> None:
    # simulate pre-commit present and subprocess.run raising -> cover except at 283-284
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "mcp_rules_assistant.hooks.shutil.which", lambda name: "/usr/bin/pre-commit",
    )

    class E(Exception):
        pass

    def bad_run(*a, **k):
        raise E("fail")

    monkeypatch.setattr("mcp_rules_assistant.hooks.run_cmd", bad_run)
    out = hooks.install_git_hooks(tmp_path)
    assert out.get("pre_commit_config")


def test_install_hooks_commit_template_outer_and_inner_except(
    monkeypatch, tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    # outer except: hooks.Path.write_text raises for commit template
    gitmsg = tmp_path / ".git" / ".gitmessage"
    real_write = hooks.Path.write_text  # type: ignore[attr-defined]

    def bad_write(self, *a, **k):  # type: ignore[override]
        if self == gitmsg:
            raise OSError("nope")
        return real_write(self, *a, **k)

    monkeypatch.setattr(hooks.Path, "write_text", bad_write)  # type: ignore[attr-defined]

    # inner except: git config raises（即便 outer except 命中，保持健壮性）
    def bad_run(*a, **k):
        raise RuntimeError("git cfg bad")

    monkeypatch.setattr("mcp_rules_assistant.hooks.run_cmd", bad_run)
    # call
    out = hooks.install_git_hooks(tmp_path)
    # even if exceptions occur, function should return minimal dict
    assert out.get("pre_commit_config") and out.get("pre_push")
