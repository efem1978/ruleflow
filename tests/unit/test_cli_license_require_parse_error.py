from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_license_require_on_off_parse_error(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".mcp").mkdir(parents=True, exist_ok=True)
        # invalid YAML to trigger parse except branch in both on/off
        Path(".mcp/assistant.yaml").write_text(": {", encoding="utf-8")
        r1 = runner.invoke(app, ["license-require-on"])
        assert r1.exit_code == 0
        r2 = runner.invoke(app, ["license-require-off"])
        assert r2.exit_code == 0
