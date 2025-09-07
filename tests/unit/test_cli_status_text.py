from __future__ import annotations

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_status_update_text(tmp_path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        r = runner.invoke(app, ["status-update", "--text"])
        assert r.exit_code == 0
