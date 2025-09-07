from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def _write_cov_xml(path: Path) -> None:
    text = (
        "<coverage>\n"
        "  <packages><package><classes>\n"
        '    <class filename="pkg/a.py" line-rate="0.905"/>\n'
        '    <class filename="pkg/b.py" line-rate="0.880"/>\n'
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    path.write_text(text, encoding="utf-8")


def test_cli_coverage_report_json(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".mcp").mkdir(parents=True, exist_ok=True)
        Path(".mcp/assistant.yaml").write_text(
            "performance:\n  on_push:\n    coverage: {min_module: 0.90}\n",
            encoding="utf-8",
        )
        _write_cov_xml(Path("coverage.xml"))
        r = runner.invoke(app, ["coverage-report", "--json"])
        assert r.exit_code == 0
        out = r.stdout or ""
        assert '"weak"' in out and '"groups"' in out and '"near"' in out
