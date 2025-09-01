from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_initialize_and_ping_and_tools(tmp_path: Path) -> None:
    srv = JsonRpcServer(); srv.project_root = tmp_path
    r1 = srv.handle(_req('initialize'))
    assert r1.get('result', {}).get('server') == 'mcp-rules-assistant'
    r2 = srv.handle(_req('ping'))
    assert r2.get('result', {}).get('ok') is True
    r3 = srv.handle(_req('tools/list'))
    assert isinstance(r3.get('result', {}).get('tools'), list)


def test_memory_and_rules_unknown_resource(tmp_path: Path) -> None:
    srv = JsonRpcServer(); srv.project_root = tmp_path
    # memory resource
    rlist = srv.handle(_req('resources/list'))
    mem_uri = next(u.get('uri') for u in rlist.get('result', {}).get('resources', []) if str(u.get('uri')).startswith('memory://'))
    rmem = srv.handle(_req('resources/read', {"uri": mem_uri}))
    assert rmem.get('result', {}).get('mimeType') == 'application/json'
    # unknown rules resource
    rid = srv._project_id()
    bad_uri = f"rules://project/{rid}/unknown"
    err = srv.handle(_req('resources/read', {"uri": bad_uri}))
    assert 'error' in err


def test_fs_apply_patch_paths(tmp_path: Path) -> None:
    srv = JsonRpcServer(); srv.project_root = tmp_path
    # dry run with maxFiles guard hit
    try:
        srv._call_tool('fs.apply_patch', {"files": [{"path": "a.py", "content": "x"}, {"path": "b.py", "content": "y"}], "maxFiles": 1})
        assert False, 'expected error'
    except Exception as e:
        assert 'maxFiles' in str(e)
    # dry run, would_write populated
    out = srv._call_tool('fs.apply_patch', {"files": [{"path": "ok.py", "content": "print(1)\n"}], "dryRun": True})
    assert out.get('ok') is True and out.get('would_write')
    # run write + runChecks (not strict)
    out2 = srv._call_tool('fs.apply_patch', {"files": [{"path": "ok2.py", "content": "def add(a,b):return a+b\n"}], "runChecks": True})
    assert out2.get('ok') is True and isinstance(out2.get('checks'), dict)

