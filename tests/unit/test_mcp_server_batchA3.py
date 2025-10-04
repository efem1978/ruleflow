"""Batch A3: push mcp_server coverage further (handle mappings, resources list/read paths)."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from unittest import mock

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _srv(tmp_path: Path, monkeypatch) -> JsonRpcServer:
    monkeypatch.chdir(tmp_path)
    return JsonRpcServer()


def test_handle_method_not_found(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    res = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "no_such_method", "params": {}})
    assert res.get("error", {}).get("code") == -32601


def test_resources_read_links(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)

    class MM:
        def snapshot(self):
            return {"links": [{"a": 1}]}

    srv.mm = MM()
    uri = f"memory://{srv._project_id()}/links"
    res = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": uri}})
    assert res.get("result", {}).get("mimeType") == "application/json"


def test_resources_read_memory_ns_not_found_maps_32001(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    uri = f"memory://{srv._project_id()}/rollup?ns=absent"
    out = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": uri}})
    assert out.get("error", {}).get("code") == -32001


def test_resources_list_symlink_untrusted_and_hardlink_denied(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    mcp = tmp_path / ".mcp"
    mcp.mkdir(exist_ok=True)
    # create a symlinked namespaced file
    real = mcp / "ns.json"
    real.write_text("{}", encoding="utf-8")
    sym = mcp / "memory.ns3.json"
    sym.symlink_to(real)

    # Also create another regular file whose stat().st_nlink we will fake >1
    f_hl = mcp / "memory.ns4.json"
    f_hl.write_text("{}", encoding="utf-8")

    orig_stat = Path.stat

    class Stat:
        def __init__(self, base):
            self._base = base
            self.st_nlink = getattr(base, "st_nlink", 1)

    def fake_stat(self):
        s = orig_stat(self)
        if self == f_hl:
            ns = Stat(s)
            ns.st_nlink = 2  # simulate hardlink count > 1
            return ns
        return s

    monkeypatch.setattr(Path, "stat", fake_stat)
    # Ensure symlinks are NOT trusted and hardlinks NOT allowed
    monkeypatch.delenv("MCP_MEMORY_TRUST_SYMLINK", raising=False)
    monkeypatch.delenv("MCP_MEMORY_TRUST_HARDLINK", raising=False)

    res = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}})
    uris = [r.get("uri", "") for r in res.get("result", {}).get("resources", [])]
    # Neither ns3 nor ns4 should be listed as namespaced entries
    assert all("ns=ns3" not in u and "ns=ns4" not in u for u in uris)
