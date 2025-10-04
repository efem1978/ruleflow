from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_rules_explain_text_includes_maxima_keys(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        m = Path(".mcp")
        m.mkdir(parents=True, exist_ok=True)
        (m / "rules_compiled.json").write_text(
            '{"policy": {"coverage.min_module": 0.9}, "meta": {"maxima": {"coverage.max_module": 0.95}}, "suggestions": [{"key":"a","severity":"info"}]}',
            encoding="utf-8",
        )
        r = runner.invoke(app, ["rules-explain"])
        assert r.exit_code == 0
        out = r.stdout or ""
        assert "maxima_keys:" in out
