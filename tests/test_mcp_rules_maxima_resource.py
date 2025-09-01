from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_rules_maxima_resource(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # write compiled with maxima
    d = tmp_path / '.mcp'
    d.mkdir(parents=True, exist_ok=True)
    (d / 'rules_compiled.json').write_text(
        '{"meta": {"maxima": {"coverage.max_module": 0.95, "coverage.max_core": 0.97}}}',
        encoding='utf-8'
    )
    rlist = srv.handle(_req('resources/list'))
    uris = [r.get('uri') for r in rlist.get('result', {}).get('resources', [])]
    max_uri = next(u for u in uris if str(u).endswith('/maxima'))
    r = srv.handle(_req('resources/read', {"uri": max_uri}))
    data = json.loads(r.get('result', {}).get('text') or '{}')
    assert 'maxima' in data and data['maxima'].get('coverage.max_module') == 0.95

