"""Batch A4: fill remaining coverage gaps in mcp_server."""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

import mcp_rules_assistant.mcp_server as ms
from mcp_rules_assistant.mcp_server import JsonRpcServer


def _srv(tmp_path: Path, monkeypatch) -> JsonRpcServer:
    monkeypatch.chdir(tmp_path)
    return JsonRpcServer()


def test_dashboard_append_info_string_items_normalized(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    status = dash / "status.json"
    status.write_text(json.dumps({"info": ["legacy", {"text": "obj"}]}), encoding="utf-8")
    srv._dashboard_append_info("new-entry", action="act")
    data = json.loads(status.read_text(encoding="utf-8"))
    assert isinstance(data.get("info"), list) and any(isinstance(x, dict) for x in data["info"]) and any(x.get("text") == "legacy" for x in data["info"] if isinstance(x, dict))


def test_security_audit_report_counts(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    p = dash / "security_audit.jsonl"
    lines = [
        "not-json\n",
        json.dumps({"event": ""}) + "\n",
        json.dumps({"event": "login"}) + "\n",
    ]
    p.write_text("".join(lines), encoding="utf-8")
    out = srv._call_tool("security.audit_report", {})
    assert out.get("ok") is True and out.get("counts", {}).get("login") == 1 and out.get("total") == 1


def test_resources_list_stat_exception_branch(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    mcp = tmp_path / ".mcp"
    mcp.mkdir(exist_ok=True)
    fn = mcp / "memory.zz.json"
    fn.write_text("{}", encoding="utf-8")
    # Patch the concrete class' stat to raise only for our file
    cls = fn.__class__
    original_stat = cls.stat

    def bad_stat(self, *a, **k):
        if self == fn:
            raise OSError("stat fail")
        return original_stat(self, *a, **k)

    monkeypatch.setattr(cls, "stat", bad_stat)
    res = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}})
    assert "resources" in res.get("result", {})


essential_policy = {
    "policy": {
        "coverage.min_module": 0.91,
        "coverage.min_core": 0.92,
        ms.POLICY_KEY_SECURITY_SAST_STRICT: True,
    }
}


def test_rules_enforce_dashboard_log_exception(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    compiled = tmp_path / ms.ri.COMPILED_JSON
    compiled.parent.mkdir(parents=True, exist_ok=True)
    compiled.write_text(json.dumps(essential_policy, ensure_ascii=False), encoding="utf-8")
    with mock.patch.object(srv, "_dashboard_append_info", side_effect=RuntimeError("log fail")):
        out = srv._call_tool("rules.enforce", {})
    assert out.get("ok") is True and "updated" in out


def test_project_switch_allow_cfg_exception_without_strict(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)

    class BadCfg:
        def get(self, *a, **k):
            raise RuntimeError("badcfg")

    srv.cfg = BadCfg()  # triggers allow_cfg except branch
    # Not setting strict env; just ensure code path executes and switch succeeds
    newp = tmp_path / "ps"
    res = srv._call_tool("project.switch", {"path": str(newp)})
    assert res.get("ok") is True and Path(res.get("root")).resolve() == newp.resolve()
