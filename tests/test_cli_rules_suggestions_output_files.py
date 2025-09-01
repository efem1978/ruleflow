from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_rules_suggestions_write_files(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        m = Path('.mcp'); m.mkdir(parents=True, exist_ok=True)
        (m / 'rules_compiled.json').write_text(
            '{"suggestions": ['
            '{"key":"k1","action":"enforce","severity":"must","value":0.9},'
            '{"key":"k2","action":"monitor","severity":"info","value":0.95}]}'
            , encoding='utf-8')
        out_json = Path('sugg.json')
        out_csv = Path('sugg.csv')
        rj = runner.invoke(app, ['rules-suggestions', '--format', 'json', '--output', str(out_json)])
        assert rj.exit_code == 0 and out_json.exists()
        rc = runner.invoke(app, ['rules-suggestions', '--format', 'csv', '--output', str(out_csv)])
        assert rc.exit_code == 0 and out_csv.exists()

