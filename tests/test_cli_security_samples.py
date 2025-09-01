from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_insert_security_samples() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        r = runner.invoke(app, ["insert-security-samples"])
        assert r.exit_code == 0
        s = Path(".semgrep.yml").read_text(encoding="utf-8")
        h = Path(".hadolint.yaml").read_text(encoding="utf-8")
        assert "rules:" in s and "py-no-eval" in s
        assert "ignored:" in h and "DL3008" in h
