"""Batch A5: push mcp_server.py to >=98% by covering remaining edges."""
from __future__ import annotations

import builtins
import io
import json
import os
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

import mcp_rules_assistant.mcp_server as ms
from mcp_rules_assistant.mcp_server import JsonRpcServer, serve_stdio


def _srv(tmp_path: Path, monkeypatch) -> JsonRpcServer:
    monkeypatch.chdir(tmp_path)
    return JsonRpcServer()


def test_security_audit_report_file_missing_returns_default(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    out = srv._call_tool("security.audit_report", {})
    assert out == {"ok": True, "counts": {}, "last": [], "total": 0}


def test_resources_list_hardlink_allowed(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    mcp = tmp_path / ".mcp"
    mcp.mkdir(exist_ok=True)
    f = mcp / "memory.ok.json"
    f.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("MCP_MEMORY_TRUST_HARDLINK", "1")
    monkeypatch.delenv("MCP_MEMORY_TRUST_SYMLINK", raising=False)
    # Create a real hardlink to ensure st_nlink > 1 for f
    hl = mcp / "hl.tmp"
    os.link(str(f), str(hl))
    res = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}})
    uris = [r.get("uri", "") for r in res.get("result", {}).get("resources", [])]
    assert any(u.endswith("ns=ok") for u in uris)


def test_memory_write_allowed_env_exceptions_paths(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    # Disable strict and allow envs; we simulate exceptions on env reads instead
    monkeypatch.delenv("MCP_STRICT_ISOLATION", raising=False)
    monkeypatch.delenv("RULEFLOW_ALLOW_MEMORY_APPEND", raising=False)
    monkeypatch.delenv("MCP_MEMORY_HARD_DISABLE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    orig_get = os.environ.get

    def guarded_get(key: str, default: Any = None):
        if key in {"PYTEST_CURRENT_TEST", "MCP_MEMORY_HARD_DISABLE", "RULEFLOW_ALLOW_MEMORY_APPEND"}:
            raise RuntimeError("env boom")
        return orig_get(key, default)

    monkeypatch.setattr(os.environ, "get", guarded_get, raising=False)
    srv.cfg = {}  # ensure final allow_write path returns False
    assert srv._memory_write_allowed() is False


class _FakeIn:
    def __init__(self, lines):
        self._lines = lines

    def __iter__(self):
        return iter(self._lines)


def test_serve_stdio_parse_error_broken_pipe(monkeypatch):
    # One invalid JSON line triggers parse error, then print raises BrokenPipeError
    fake_stdin = _FakeIn(["{invalid json}\n"])  # JSONDecodeError

    def bad_print(*a, **k):
        raise BrokenPipeError

    monkeypatch.setattr(ms.sys, "stdin", fake_stdin)
    monkeypatch.setattr(builtins, "print", bad_print)
    # Should return cleanly (no exception) due to BrokenPipe handling
    serve_stdio()


def test_serve_stdio_response_broken_pipe(monkeypatch):
    # Valid request leading to response printing where print raises BrokenPipeError
    req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "no_such_method", "params": {}}) + "\n"
    fake_stdin = _FakeIn([req])
    calls = {"n": 0}

    def guarded_print(*a, **k):
        # Allow first print call inside parse path to succeed if any; raise on response print
        calls["n"] += 1
        if calls["n"] >= 1:
            raise BrokenPipeError
        return None

    monkeypatch.setattr(ms.sys, "stdin", fake_stdin)
    monkeypatch.setattr(builtins, "print", guarded_print)
    # Should exit cleanly on BrokenPipeError while printing response
    serve_stdio()
