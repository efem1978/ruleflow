from __future__ import annotations

import io
import sys
from pathlib import Path

import mcp_rules_assistant.mcp_server as msv


def test_handle_unknown_method_and_resource(tmp_path: Path) -> None:
    srv = msv.JsonRpcServer(); srv.project_root = tmp_path
    res1 = srv.handle({"jsonrpc":"2.0","id":1,"method":"nope","params":{}})
    assert 'error' in res1
    res2 = srv.handle({"jsonrpc":"2.0","id":1,"method":"resources/read","params":{"uri":"foo://whatever"}})
    assert 'error' in res2


def test_env_prepare_exception_path(monkeypatch, tmp_path: Path) -> None:
    srv = msv.JsonRpcServer(); srv.project_root = tmp_path
    class Boom(Exception): pass
    def boom_run(*a, **k):
        raise Boom('x')
    import subprocess
    monkeypatch.setattr(subprocess, 'run', boom_run)
    out = srv._call_tool('env.prepare', {"create": True, "install": True})
    assert out.get('ok') is False and 'env prepare failed' in (out.get('message') or '')


def test_env_diagnose_invalid_maxima(tmp_path: Path) -> None:
    srv = msv.JsonRpcServer(); srv.project_root = tmp_path
    (tmp_path / '.mcp').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.mcp/rules_compiled.json').write_text('{invalid', encoding='utf-8')
    out = srv._call_tool('env.diagnose', {})
    assert out.get('ok') is True and isinstance(out.get('maxima'), dict)


def test_rules_maxima_tool_missing_and_invalid(tmp_path: Path) -> None:
    srv = msv.JsonRpcServer(); srv.project_root = tmp_path
    r1 = srv._call_tool('rules.maxima', {})
    assert r1.get('ok') is False
    (tmp_path / '.mcp').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.mcp/rules_compiled.json').write_text('{invalid', encoding='utf-8')
    r2 = srv._call_tool('rules.maxima', {})
    assert r2.get('ok') is True and r2.get('maxima') == {}


def test_plan_update_missing_text(tmp_path: Path) -> None:
    srv = msv.JsonRpcServer(); srv.project_root = tmp_path
    try:
        srv._call_tool('plan.update', {})
        assert False, 'expected error'
    except Exception as e:
        assert 'text required' in str(e)


def test_config_get_and_update_invalid_yaml(tmp_path: Path) -> None:
    srv = msv.JsonRpcServer(); srv.project_root = tmp_path
    cfg = tmp_path / '.mcp/assistant.yaml'; cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text('::not yaml::', encoding='utf-8')
    r = srv._call_tool('config.get', {"section": None})
    assert r.get('ok') is True and isinstance(r.get('config'), dict)
    r2 = srv._call_tool('config.update', {"data": {"hadolint": True}})
    assert r2.get('ok') is True


def test_serve_stdio_parse_error_and_blank(monkeypatch) -> None:
    bad = 'not json\n\n' + '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}\n'
    fake_stdin = io.StringIO(bad)
    buf = io.StringIO()
    class _W(io.StringIO):
        def write(self, s):
            buf.write(s)
            return len(s)
    monkeypatch.setattr(sys, 'stdin', fake_stdin)
    old = sys.stdout; sys.stdout = _W()
    try:
        msv.serve_stdio()
    finally:
        sys.stdout = old
    text = buf.getvalue()
    assert 'Parse error' in text and '"result":{"ok":true}' in text.replace(' ','').lower()

