from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_rules_onboard_invalid_inputs(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        r = runner.invoke(
            app,
            [
                "rules-onboard",
                "--scenario",
                "unknown-scenario",
                "--complexity",
                "unknown-size",
                "--dev-mode",
                "tdd",
                "--dry-run",
            ],
        )
        assert r.exit_code == 0
        out = r.stdout or r.output
        assert "回退到 personal/small" in out
