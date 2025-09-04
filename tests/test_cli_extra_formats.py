from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def _write_cov_xml(path: Path) -> None:
    path.write_text(
        (
            "<coverage>\n"
            "  <packages><package><classes>\n"
            "    <class filename=\"near1.py\" line-rate=\"0.905\" lines-valid=\"100\" lines-covered=\"90\"/>\n"
            "    <class filename=\"near2.py\" line-rate=\"0.920\" lines-valid=\"100\" lines-covered=\"92\"/>\n"
            "  </classes></package></packages>\n"
            "</coverage>\n"
        ),
        encoding="utf-8",
    )


def test_cli_coverage_near_formats_and_outputs(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path('.mcp').mkdir(parents=True, exist_ok=True)
        # set low threshold to ensure 'near' entries exist
        Path('.mcp/assistant.yaml').write_text('performance:\n  on_push:\n    coverage: {min_module: 0.90}\n', encoding='utf-8')
        _write_cov_xml(Path('coverage.xml'))
        # json to stdout + policy_prefix filter
        rj = runner.invoke(app, ['coverage-near', '--within', '3', '--top', '20', '--format', 'json', '--policy-prefix', 'n'])
        assert rj.exit_code == 0
        out = rj.stdout.strip()
        assert out.startswith('[') and out.endswith(']')
        # csv to file
        out_csv = Path('near.csv')
        rc = runner.invoke(app, ['coverage-near', '--within', '3', '--top', '20', '--format', 'csv', '--output', str(out_csv)])
        assert rc.exit_code == 0 and out_csv.exists()
        text = out_csv.read_text(encoding='utf-8')
        assert 'file,coverage,threshold,delta_up' in text.splitlines()[0]
        # json to file
        out_json = Path('near.json')
        rj2 = runner.invoke(app, ['coverage-near', '--within', '3', '--top', '20', '--format', 'json', '--output', str(out_json)])
        assert rj2.exit_code == 0 and out_json.exists()


def test_cli_diagnose_text(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path('.mcp').mkdir(parents=True, exist_ok=True)
        Path('.mcp/assistant.yaml').write_text('performance:\n  on_push:\n    coverage: {min_module: 0.90}\n', encoding='utf-8')
        r = runner.invoke(app, ['diagnose', '--text'])
        assert r.exit_code == 0
        out = r.stdout or ''
        assert 'Diagnose' in out and 'coverage.xml exists' in out
