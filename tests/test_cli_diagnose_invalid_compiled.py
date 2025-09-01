from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_diagnose_handles_invalid_compiled_json(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path('.mcp').mkdir(parents=True, exist_ok=True)
        Path('.mcp/rules_compiled.json').write_text('{invalid', encoding='utf-8')
        r = runner.invoke(app, ['diagnose', '--json'])
        assert r.exit_code == 0
        # maxima should fallback to {}
        assert '"maxima":' in (r.stdout or '')

