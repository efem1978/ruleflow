from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def _write_cov_xml(path: Path) -> None:
    path.write_text(
        "<coverage>\n  <packages><package><classes>\n"
        "<class filename=\"x.py\" line-rate=\"0.905\"/>\n"
        "</classes></package></packages>\n</coverage>\n",
        encoding='utf-8'
    )


def test_tools_coverage_report_and_rules_maxima(tmp_path: Path) -> None:
    srv = JsonRpcServer(); srv.project_root = tmp_path
    # config & coverage
    (tmp_path / '.mcp').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.mcp/assistant.yaml').write_text('performance:\n  on_push:\n    coverage: {min_module: 0.90}\n', encoding='utf-8')
    _write_cov_xml(tmp_path / 'coverage.xml')
    r = srv.handle(_req('tools/call', {"name": "coverage.report", "arguments": {}}))
    rep = r.get('result', {})
    assert rep.get('ok') is True and isinstance(rep.get('weak'), list) and isinstance(rep.get('near'), list)
    # maxima
    (tmp_path / '.mcp/rules_compiled.json').write_text('{"meta": {"maxima": {"coverage.max_module": 0.95}}}', encoding='utf-8')
    r2 = srv.handle(_req('tools/call', {"name": "rules.maxima", "arguments": {}}))
    mx = r2.get('result', {})
    assert mx.get('ok') is True and mx.get('maxima', {}).get('coverage.max_module') == 0.95

