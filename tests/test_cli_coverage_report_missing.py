from __future__ import annotations

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_coverage_report_missing_xml(tmp_path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        r = runner.invoke(app, ["coverage-report", "--json"])
        assert r.exit_code != 0
        assert "coverage.xml" in (r.stdout or "")
