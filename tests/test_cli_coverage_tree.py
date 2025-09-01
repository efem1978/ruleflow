from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def _write_cov_xml(path: Path) -> None:
    text = (
        "<coverage>\n"
        "  <packages><package><classes>\n"
        "    <class filename=\"pkg/a/core.py\" line-rate=\"0.80\" lines-valid=\"10\" lines-covered=\"8\"/>\n"
        "    <class filename=\"pkg/b/mod.py\" line-rate=\"0.85\" lines-valid=\"20\" lines-covered=\"17\"/>\n"
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    path.write_text(text, encoding="utf-8")


def test_cli_coverage_tree(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        _write_cov_xml(Path("coverage.xml"))
        r = runner.invoke(app, ["coverage-tree"])
        assert r.exit_code == 0
        out = r.stdout or ""
        assert "pkg/" in out or "pkg" in out
