from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_ingest_rules_conflicts(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        d = Path('rules.md')
        # two conflicting min_module values -> conflicts present
        d.write_text('- 覆盖率 90%\n- 覆盖率 80%\n', encoding='utf-8')
        r = runner.invoke(app, ['ingest-rules', str(d)])
        assert r.exit_code == 0
        out = r.stdout or ''
        assert '存在规则冲突' in out


def _write_cov_xml(path: Path, a: float = 0.99) -> None:
    path.write_text(
        "<coverage>\n  <packages><package><classes>\n"
        f"<class filename=\"a.py\" line-rate=\"{a:.3f}\"/>\n"
        "</classes></package></packages>\n</coverage>\n",
        encoding='utf-8'
    )


def test_cli_rules_explain_text_with_suggestions(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        m = Path('.mcp'); m.mkdir(parents=True, exist_ok=True)
        (m/'rules_compiled.json').write_text(
            '{"policy":{"coverage.min_module":0.90},"suggestions":[{"key":"coverage.min_module","action":"enforce","severity":"must","value":0.9}]}'
            , encoding='utf-8')
        r = runner.invoke(app, ['rules-explain', '--with-suggestions', 'short'])
        assert r.exit_code == 0
        assert 'suggestions_keys:' in (r.stdout or '')


def test_cli_coverage_near_missing_and_nonear(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # near without coverage.xml -> exit 1 and message
        r1 = runner.invoke(app, ['coverage-near'])
        assert r1.exit_code != 0 and ('coverage.xml 不存在' in (r1.stdout or '') or 'coverage.xml not found' in (r1.stdout or ''))

        # near with no near files -> prints none
        Path('.mcp').mkdir(parents=True, exist_ok=True)
        Path('.mcp/assistant.yaml').write_text('performance:\n  on_push:\n    coverage: {min_module: 0.90}\n', encoding='utf-8')
        _write_cov_xml(Path('coverage.xml'), a=0.99)
        r2 = runner.invoke(app, ['coverage-near', '--within', '1'])
        assert r2.exit_code == 0
        assert '无近阈值文件' in (r2.stdout or '')

