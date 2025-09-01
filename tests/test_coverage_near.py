from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer
from mcp_rules_assistant.cli import app
from typer.testing import CliRunner


def _write_cov_xml(path: Path) -> None:
    text = (
        "<coverage>\n"
        "  <packages><package><classes>\n"
        "    <class filename=\"pkg/a.py\" line-rate=\"0.920\"/>\n"
        "    <class filename=\"pkg/b.py\" line-rate=\"0.905\"/>\n"
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    path.write_text(text, encoding="utf-8")


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_mcp_near_resource(tmp_path: Path) -> None:
    _write_cov_xml(tmp_path / 'coverage.xml')
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # Set module threshold 0.90
    cfg = tmp_path / '.mcp/assistant.yaml'
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text('performance:\n  on_push:\n    coverage: {min_module: 0.90}\n', encoding='utf-8')
    rlist = srv.handle(_req('resources/list'))
    near_uri = next(r.get('uri') for r in rlist.get('result', {}).get('resources', []) if str(r.get('uri')).endswith('/near'))
    r = srv.handle(_req('resources/read', {"uri": near_uri}))
    data = json.loads(r.get('result', {}).get('text') or '{}')
    assert data.get('ok') is True
    near = data.get('near') or []
    # pkg/b.py is 0.905 (above 0.9 within 0.03): should appear
    assert any(it.get('file') == 'pkg/b.py' for it in near)


def test_cli_coverage_near(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path('.mcp').mkdir(parents=True, exist_ok=True)
        Path('.mcp/assistant.yaml').write_text('performance:\n  on_push:\n    coverage: {min_module: 0.90}\n', encoding='utf-8')
        _write_cov_xml(Path('coverage.xml'))
        r = runner.invoke(app, ['coverage-near', '--within', '3', '--top', '10'])
        assert r.exit_code == 0
        out = r.stdout or ''
        assert 'pkg/b.py' in out


def test_cli_coverage_near_with_prefix_filter(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path('.mcp').mkdir(parents=True, exist_ok=True)
        Path('.mcp/assistant.yaml').write_text('performance:\n  on_push:\n    coverage: {min_module: 0.90}\n', encoding='utf-8')
        _write_cov_xml(Path('coverage.xml'))
        # Add an extra near file under other/
        cov = Path('coverage.xml')
        cov.write_text(
            "<coverage>\n  <packages><package><classes>\n"
            "<class filename=\"pkg/a.py\" line-rate=\"0.920\"/>\n"
            "<class filename=\"pkg/b.py\" line-rate=\"0.905\"/>\n"
            "<class filename=\"other/c.py\" line-rate=\"0.905\"/>\n"
            "</classes></package></packages>\n</coverage>\n",
            encoding='utf-8'
        )
        r = runner.invoke(app, ['coverage-near', '--within', '3', '--top', '10', '--policy-prefix', 'pkg/'])
        assert r.exit_code == 0
        out = r.stdout or ''
        assert 'pkg/b.py' in out and 'other/c.py' not in out


def test_cli_coverage_near_json_and_csv(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path('.mcp').mkdir(parents=True, exist_ok=True)
        Path('.mcp/assistant.yaml').write_text('performance:\n  on_push:\n    coverage: {min_module: 0.90}\n', encoding='utf-8')
        _write_cov_xml(Path('coverage.xml'))
        rj = runner.invoke(app, ['coverage-near', '--within', '3', '--format', 'json'])
        assert rj.exit_code == 0
        assert 'pkg/b.py' in (rj.stdout or '')
        # write to files
        out_json = Path('near.json')
        out_csv = Path('near.csv')
        rjf = runner.invoke(app, ['coverage-near', '--within', '3', '--format', 'json', '--output', str(out_json)])
        assert rjf.exit_code == 0 and out_json.exists()
        textj = out_json.read_text(encoding='utf-8')
        assert 'pkg/b.py' in textj
        rc = runner.invoke(app, ['coverage-near', '--within', '3', '--format', 'csv', '--output', str(out_csv)])
        assert rc.exit_code == 0
        assert out_csv.exists()
        outc = out_csv.read_text(encoding='utf-8')
        assert 'file,coverage,threshold,delta_up' in outc



def test_cli_coverage_near_within_min_clamped(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path('.mcp').mkdir(parents=True, exist_ok=True)
        Path('.mcp/assistant.yaml').write_text("performance:\n  on_push:\n    coverage: {min_module: 0.90}\n", encoding='utf-8')
        # file at 0.909 (0.9% above threshold) should be included when within is clamped to 1%
        Path('coverage.xml').write_text(
            "<coverage>\n  <packages><package><classes>\n<class filename=\"x.py\" line-rate=\"0.909\"/>\n</classes></package></packages>\n</coverage>\n",
            encoding='utf-8'
        )
        r = runner.invoke(app, ['coverage-near', '--within', '0.5'])
        assert r.exit_code == 0
        assert 'x.py' in (r.stdout or '')
