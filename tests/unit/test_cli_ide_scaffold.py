from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_ide_scaffold_vscode(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        r = runner.invoke(app, ["ide-scaffold", "--editor", "vscode"])
        assert r.exit_code == 0
        assert (root / ".mcp/ide/vscode/settings.sample.json").exists()
        assert (root / ".mcp/ide/vscode/README.md").exists()
