from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner
import types

from mcp_rules_assistant.cli import app


def test_cli_diagnose_with_maxima(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path('.mcp').mkdir(parents=True, exist_ok=True)
        Path('.mcp/rules_compiled.json').write_text(
            '{"meta": {"maxima": {"coverage.max_module": 0.95}}}', encoding='utf-8')
        r = runner.invoke(app, ['diagnose', '--json'])
        assert r.exit_code == 0
        assert '"maxima"' in (r.stdout or '')


def test_cli_coverage_clean_cache_unlink_error(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        cache = Path('.mcp/coverage_cache.json')
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text('{}', encoding='utf-8')
        # make unlink raise
        def boom(self):
            raise OSError('EACCES')
        monkeypatch.setattr(type(cache), 'unlink', boom)
        r = runner.invoke(app, ['coverage-clean-cache'])
        assert r.exit_code != 0
        assert '删除失败' in (r.stdout or '')


def test_cli_ci_set_invalid_yaml(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        p = Path('.mcp/assistant.yaml')
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('::invalid::', encoding='utf-8')
        r = runner.invoke(app, ['ci-set', '--hadolint'])
        # Should still succeed (parser except -> {})
        assert r.exit_code == 0


def test_cli_prepare_env_dry_with_python(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        r = runner.invoke(app, ['prepare-env', '--python', 'python3', '--dry-run'])
        assert r.exit_code == 0
        assert 'venv' in (r.stdout or '')


def test_cli_coverage_near_set_invalid_yaml(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        p = Path('.mcp/assistant.yaml')
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('::::', encoding='utf-8')
        r = runner.invoke(app, ['coverage-near-set', '--within', '4', '--top', '7'])
        assert r.exit_code == 0
        out = Path('.mcp/assistant.yaml').read_text(encoding='utf-8')
        assert 'near:' in out

