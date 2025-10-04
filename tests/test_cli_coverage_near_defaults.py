from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_coverage_near_uses_config_defaults(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".mcp").mkdir(parents=True, exist_ok=True)
        Path(".mcp/assistant.yaml").write_text(
            "performance:\n  on_push:\n    coverage: {min_module: 0.90}\ncoverage:\n  near: {within: 0.05, top: 1}\n",
            encoding="utf-8",
        )
        Path("coverage.xml").write_text(
            "<coverage>\n  <packages><package><classes>\n"
            '<class filename="n.py" line-rate="0.905"/>\n'
            '<class filename="f.py" line-rate="0.80"/>\n'
            "</classes></package></packages>\n</coverage>\n",
            encoding="utf-8",
        )
        r = runner.invoke(app, ["coverage-near"])
        assert r.exit_code == 0
        out = r.stdout or ""
        assert "n.py" in out and "f.py" not in out
