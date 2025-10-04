from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def _write_cov_xml(path: Path) -> None:
    text = (
        "<coverage>\n"
        "  <packages><package><classes>\n"
        '    <class filename="mcp_rules_assistant/foo.py" line-rate="0.91" lines-valid="100" lines-covered="91"/>\n'
        '    <class filename="other/bar.py" line-rate="0.88" lines-valid="100" lines-covered="88"/>\n'
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    path.write_text(text, encoding="utf-8")


def test_cli_coverage_prints_delta(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # thresholds: module 90%, assistant module 95%
        cfg = Path(".mcp/assistant.yaml")
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(
            "coverage:\n  policy:\n    'mcp_rules_assistant/': 0.95\n", encoding="utf-8",
        )
        _write_cov_xml(Path("coverage.xml"))
        r = runner.invoke(app, ["coverage"])
        assert r.exit_code == 0
        out = r.stdout or ""
        # Expect delta symbol and percentage
        assert "Δ" in out and "%" in out
