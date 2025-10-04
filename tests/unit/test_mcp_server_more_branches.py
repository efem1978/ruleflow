"""More targeted coverage for mcp_server edge branches."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer
import mcp_rules_assistant.mcp_server as ms


def _srv(tmp_path: Path, monkeypatch) -> JsonRpcServer:
    monkeypatch.chdir(tmp_path)
    srv = JsonRpcServer()
    assert srv.project_root == tmp_path
    return srv


def test_security_audit_report_exception(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    p = dash / "security_audit.jsonl"
    p.write_text("{}\n", encoding="utf-8")

    # make reading this file fail to trigger except path → {ok: False}
    original_read_text = Path.read_text

    def bad_read(self, *args, **kwargs):
        if self == p:
            raise OSError("read fail")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", bad_read)
    out = srv._call_tool("security.audit_report", {})
    assert out == {"ok": False}


def test_rules_resolve_counts_and_dashboard_log_exception(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    compiled = tmp_path / ".mcp" / "rules_compiled.json"
    compiled.parent.mkdir(parents=True, exist_ok=True)
    compiled.write_text(
        json.dumps({"conflicts": [1, 2], "suggestions": [3]}, ensure_ascii=False),
        encoding="utf-8",
    )

    # Avoid real enforcement complexity: stub _tool_rules_enforce
    with mock.patch.object(srv, "_tool_rules_enforce", return_value={"enforced": ["a", "b"]}):
        # Trigger _dashboard_append_info exception branch
        with mock.patch.object(srv, "_dashboard_append_info", side_effect=RuntimeError("boom")):
            out = srv._call_tool("rules.resolve", {})
    assert out.get("conflicts") == 2 and out.get("suggestions") == 1


def test_memory_append_turn_denied_audit_exception(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    # Disallow writes
    monkeypatch.setattr(srv, "_memory_write_allowed", lambda: False)
    # Make _audit raise so the except: pass path is taken
    with mock.patch.object(ms, "_audit", side_effect=RuntimeError("audit fail")):
        out = srv._call_tool(
            "memory.append_turn",
            {"role": "user", "content": "hi", "meta": {"k": 1}},
        )
    assert out.get("ok") is False and out.get("error") == "memory_write_disabled"


def test_project_switch_strict_denied_audit_exception(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    monkeypatch.delenv("MCP_ALLOW_PROJECT_SWITCH", raising=False)
    monkeypatch.setenv("MCP_STRICT_ISOLATION", "1")
    # Make _audit raise to cover except branch
    with mock.patch.object(ms, "_audit", side_effect=RuntimeError("audit fail")):
        with pytest.raises(ValueError):
            srv._call_tool("project.switch", {"path": str(tmp_path / "newproj")})


def test_resources_read_unknown_uri_maps_error(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    req = {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "unknown://x"}}
    res = srv.handle(req)
    assert res.get("error", {}).get("code") == -32000
