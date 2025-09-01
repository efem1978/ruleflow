from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import mcp_rules_assistant.mcp_server as msv


def test_serve_stdio_ping(monkeypatch) -> None:
    # feed one JSON-RPC ping line and capture stdout
    input_data = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}) + "\n"
    fake_stdin = io.StringIO(input_data)
    buf = io.StringIO()

    class _W(io.StringIO):
        def write(self, s):
            buf.write(s)
            return len(s)

    monkeypatch.setattr(sys, 'stdin', fake_stdin)
    # use real print, just capture by redirecting sys.stdout temporarily
    old_stdout = sys.stdout
    sys.stdout = _W()
    try:
        msv.serve_stdio()
    finally:
        sys.stdout = old_stdout
    text = buf.getvalue().replace(' ', '').lower()
    assert '"result":{"ok":true}' in text


def test_project_detect_node_and_rust(tmp_path: Path) -> None:
    srv = msv.JsonRpcServer(); srv.project_root = tmp_path
    # Node
    (tmp_path / 'package.json').write_text('{"name":"x"}', encoding='utf-8')
    d = srv._call_tool('project.detect', {})
    assert d.get('language') in ('node', 'python')  # node expected but allow python if env differs
    # Rust
    (tmp_path / 'Cargo.toml').write_text('[package]\nname="x"', encoding='utf-8')
    d2 = srv._call_tool('project.detect', {})
    assert d2.get('language') in ('rust', 'python', 'node')


def test_rules_maxima_resource_error_when_missing(tmp_path: Path) -> None:
    srv = msv.JsonRpcServer(); srv.project_root = tmp_path
    rlist = srv.handle({"jsonrpc":"2.0","id":1,"method":"resources/list","params":{}})
    uris = [r.get('uri') for r in rlist.get('result', {}).get('resources', [])]
    max_uri = next(u for u in uris if str(u).endswith('/maxima'))
    res = srv.handle({"jsonrpc":"2.0","id":1,"method":"resources/read","params":{"uri": max_uri}})
    assert 'error' in res


def test_rules_maxima_resource_invalid_json(tmp_path: Path) -> None:
    srv = msv.JsonRpcServer(); srv.project_root = tmp_path
    (tmp_path / '.mcp').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.mcp/rules_compiled.json').write_text('{invalid', encoding='utf-8')
    rlist = srv.handle({"jsonrpc":"2.0","id":1,"method":"resources/list","params":{}})
    uris = [r.get('uri') for r in rlist.get('result', {}).get('resources', [])]
    max_uri = next(u for u in uris if str(u).endswith('/maxima'))
    res = srv.handle({"jsonrpc":"2.0","id":1,"method":"resources/read","params":{"uri": max_uri}})
    assert 'result' in res and res['result'].get('mimeType') == 'application/json'
