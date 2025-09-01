from __future__ import annotations

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_ci_set_noargs_prints_existing() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        # No config exists; running ci-set without options should print current (empty) ci dict and exit 0
        r = runner.invoke(app, ["ci-set"])  # no options
        assert r.exit_code == 0
        out = r.stdout or ''
        # 接受 Python dict 风格或 JSON 风格打印
        assert 'ci' in out and 'hadolint' in out
