from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_rules_explain_json_includes_maxima(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        m = Path('.mcp'); m.mkdir(parents=True, exist_ok=True)
        (m / 'rules_compiled.json').write_text(
            '{"policy": {"coverage.min_module": 0.9}, "meta": {"maxima": {"coverage.max_module": 0.95, "coverage.max_core": 0.97}}, "conflicts": [], "suggestions": []}',
            encoding='utf-8'
        )
        r = runner.invoke(app, ['rules-explain', '--json'])
        assert r.exit_code == 0
        jout = r.stdout or ''
        assert '"maxima"' in jout and 'coverage.max_module' in jout and '0.95' in jout

