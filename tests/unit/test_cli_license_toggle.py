from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_license_toggle_on_off(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # ensure project config exists
        (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
        # turn on
        r1 = runner.invoke(app, ["license-require-on"])
        assert r1.exit_code == 0
        text = Path(".mcp/assistant.yaml").read_text(encoding="utf-8")
        assert "required: true" in text
        # turn off
        r2 = runner.invoke(app, ["license-require-off"])
        assert r2.exit_code == 0
        text2 = Path(".mcp/assistant.yaml").read_text(encoding="utf-8")
        assert "required: false" in text2
