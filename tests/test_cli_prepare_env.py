from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_prepare_env_dry_run(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        r = runner.invoke(app, ["prepare-env", "--dry-run"])
        assert r.exit_code == 0
        out = r.stdout or ""
        # Expect dry-run plan text with venv path hint
        assert "dry" in out and ".mcp/venv" in out

