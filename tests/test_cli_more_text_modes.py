from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def _write_cov_xml(path: Path) -> None:
    path.write_text(
        (
            "<coverage>\n"
            "  <packages><package><classes>\n"
            "    <class filename=\"n1.py\" line-rate=\"0.950\" lines-valid=\"100\" lines-covered=\"95\"/>\n"
            "    <class filename=\"n2.py\" line-rate=\"0.955\" lines-valid=\"100\" lines-covered=\"95.5\"/>\n"
            "  </classes></package></packages>\n"
            "</coverage>\n"
        ),
        encoding="utf-8",
    )


def test_cli_coverage_near_text_mode(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path('.mcp').mkdir(parents=True, exist_ok=True)
        Path('.mcp/assistant.yaml').write_text('performance:\n  on_push:\n    coverage: {min_module: 0.95}\n', encoding='utf-8')
        _write_cov_xml(Path('coverage.xml'))
        r = runner.invoke(app, ['coverage-near', '--within', '3', '--top', '20'])
        assert r.exit_code == 0
        out = r.stdout or ''
        assert '近阈值文件' in out or '≥' in out  # contains text output


def test_cli_rules_suggestions_text_mode(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        m = Path('.mcp'); m.mkdir(parents=True, exist_ok=True)
        (m / 'rules_compiled.json').write_text(
            '{"suggestions": ['
            '{"key":"k1","action":"enforce","severity":"must","value":0.9},'
            '{"key":"k2","action":"monitor","severity":"info","value":0.95}]}'
            , encoding='utf-8')
        r = runner.invoke(app, ['rules-suggestions'])
        assert r.exit_code == 0
        out = r.stdout or ''
        assert 'Suggestions' in out or '建议' in out


def test_cli_coverage_near_csv_stdout(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path('.mcp').mkdir(parents=True, exist_ok=True)
        Path('.mcp/assistant.yaml').write_text('performance:\n  on_push:\n    coverage: {min_module: 0.95}\n', encoding='utf-8')
        _write_cov_xml(Path('coverage.xml'))
        r = runner.invoke(app, ['coverage-near', '--within', '3', '--top', '20', '--format', 'csv'])
        assert r.exit_code == 0
        out = r.stdout.strip().splitlines()[0]
        assert 'file,coverage,threshold,delta_up' in out


def test_cli_plan_set(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # init plan
        r1 = runner.invoke(app, ['plan-init'])
        assert r1.exit_code == 0
        r2 = runner.invoke(app, ['plan-set', '--status', 'in_progress', '--current', '编写测试', '--next-step', '生成CI'])
        assert r2.exit_code == 0
