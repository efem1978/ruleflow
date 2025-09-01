from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_rules_explain_outputs_summary(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        m = Path('.mcp'); m.mkdir(parents=True, exist_ok=True)
        (m / 'rules_compiled.json').write_text(
            '{"policy": {"coverage.min_module": 0.9, "test.no_skip_xfail": true, "security.secrets_scan": true}, "conflicts": [{"key":"x"}], "suggestions": [{}]}',
            encoding='utf-8'
        )
        r = runner.invoke(app, ['rules-explain'])
        assert r.exit_code == 0
        out = r.stdout or ''
        assert 'coverage.min_module=0.9' in out
        assert 'test.no_skip_xfail=True' in out or 'test.no_skip_xfail=true' in out
        assert 'security.secrets_scan=True' in out or 'security.secrets_scan=true' in out
        assert 'conflicts=1' in out and 'suggestions=1' in out
        rj = runner.invoke(app, ['rules-explain', '--json', '--with-suggestions', 'short'])
        assert rj.exit_code == 0
        jout = rj.stdout or ''
        assert '"conflicts": 1' in jout and '"suggestions": 1' in jout
        assert 'suggestions_keys' in jout
