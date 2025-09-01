from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def _write_cov_xml_good(path: Path) -> None:
    path.write_text(
        "<coverage>\n  <packages><package><classes>\n"
        "<class filename=\"a.py\" line-rate=\"0.990\"/>\n"
        "<class filename=\"b.py\" line-rate=\"0.980\"/>\n"
        "</classes></package></packages>\n</coverage>\n",
        encoding='utf-8'
    )


def test_cli_coverage_no_weak(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path('.mcp').mkdir(parents=True, exist_ok=True)
        Path('.mcp/assistant.yaml').write_text('performance:\n  on_push:\n    coverage: {min_module: 0.95}\n', encoding='utf-8')
        _write_cov_xml_good(Path('coverage.xml'))
        r = runner.invoke(app, ['coverage'])
        assert r.exit_code == 0
        assert '覆盖率良好' in (r.stdout or '')

