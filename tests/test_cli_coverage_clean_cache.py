from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from mcp_rules_assistant.cli import app
from mcp_rules_assistant.coverage_summary import summarize


def _write_cov_xml(path: Path) -> None:
    text = (
        "<coverage>\n"
        "  <packages><package><classes>\n"
        "    <class filename=\"a.py\" line-rate=\"0.905\"/>\n"
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    path.write_text(text, encoding="utf-8")


def test_cli_coverage_clean_cache(tmp_path: Path) -> None:
    _write_cov_xml(tmp_path / 'coverage.xml')
    # build cache by running summarize
    summarize(project_root=tmp_path)
    cache = tmp_path / '.mcp/coverage_cache.json'
    assert cache.exists()
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # copy cache into iso fs
        Path('.mcp').mkdir(parents=True, exist_ok=True)
        (Path('.mcp') / 'coverage_cache.json').write_text(cache.read_text(encoding='utf-8'), encoding='utf-8')
        r = runner.invoke(app, ['coverage-clean-cache'])
        assert r.exit_code == 0
        assert not (Path('.mcp') / 'coverage_cache.json').exists()

