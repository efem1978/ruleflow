from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_ide_scaffold_cursor_and_jetbrains_and_neovim(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    for editor in ("cursor", "jetbrains", "neovim"):
        out = srv._call_tool("ide.scaffold", {"editor": editor})
        assert out.get("ok") is True
        files = out.get("files") or []
        assert isinstance(files, list) and files
        # scaffold under .mcp/ide/<editor>
        for f in files:
            assert (tmp_path / f).exists()


def test_git_install_hooks_tool(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool("git.install_hooks", {})
    assert out.get("ok") is True
    # .pre-commit-config.yaml and .git/hooks/pre-push should exist
    assert (tmp_path / ".pre-commit-config.yaml").exists()
    assert (tmp_path / ".git" / "hooks" / "pre-push").exists()
