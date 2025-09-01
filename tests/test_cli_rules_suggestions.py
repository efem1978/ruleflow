from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_rules_suggestions_outputs(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        m = Path('.mcp'); m.mkdir(parents=True, exist_ok=True)
        (m / 'rules_compiled.json').write_text(
            '{"suggestions": ['
            '{"key":"coverage.min_module","action":"enforce","severity":"must","value":0.9,"note":"set min"},'
            '{"key":"coverage.max_module","action":"monitor","severity":"info","value":0.95,"note":"upper bound"}]}'
            , encoding='utf-8')
        r = runner.invoke(app, ['rules-suggestions'])
        assert r.exit_code == 0
        out = r.stdout or ''
        assert 'coverage.min_module' in out and 'coverage.max_module' in out
        rj = runner.invoke(app, ['rules-suggestions', '--format', 'json'])
        assert rj.exit_code == 0 and '"severity"' in (rj.stdout or '')
        rc = runner.invoke(app, ['rules-suggestions', '--format', 'csv'])
        assert rc.exit_code == 0

