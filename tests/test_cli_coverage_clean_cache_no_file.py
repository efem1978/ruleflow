from __future__ import annotations

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_coverage_clean_cache_no_file(tmp_path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        r = runner.invoke(app, ["coverage-clean-cache"])
        assert r.exit_code == 0
        assert "未找到缓存文件" in (r.stdout or "")
