"""Batch A2: cover remaining targeted branches in mcp_server."""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

import mcp_rules_assistant.mcp_server as ms
from mcp_rules_assistant.mcp_server import JsonRpcServer


def _srv(tmp_path: Path, monkeypatch) -> JsonRpcServer:
    monkeypatch.chdir(tmp_path)
    return JsonRpcServer()


def test_memory_write_allowed_cfg_errors(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    # Ensure not strict and no env allows
    monkeypatch.delenv("MCP_STRICT_ISOLATION", raising=False)
    monkeypatch.delenv("RULEFLOW_ALLOW_MEMORY_APPEND", raising=False)

    class BadCfg0:
        def get(self, *a, **k):
            # raise on cfg0.get('memory', {})
            raise RuntimeError("cfg0")

    class BadCfg:
        def get(self, *a, **k):
            # raise on cfg.get('memory', {})
            raise RuntimeError("cfg")

    # cover cfg0 except (hard_disable path)
    srv.cfg = {"memory": BadCfg0()}  # type: ignore[assignment]
    assert srv._memory_write_allowed() is False
    # cover cfg except (final allow_write path)
    srv.cfg = BadCfg()  # type: ignore[assignment]
    assert srv._memory_write_allowed() is False


def test_dashboard_append_info_write_error(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    dash = tmp_path / ".mcp" / "dashboard"
    p = dash / "status.json"
    dash.mkdir(parents=True, exist_ok=True)
    p.write_text("{}", encoding="utf-8")

    original_write = Path.write_text

    def bad_write(self, *a, **k):
        if self == p:
            raise OSError("write fail")
        return original_write(self, *a, **k)

    monkeypatch.setattr(Path, "write_text", bad_write)
    # Should not raise even when write fails (except: pass)
    srv._dashboard_append_info("hello")


def test_resources_list_skip_empty_ns(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    f = tmp_path / ".mcp" / "memory..json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("{}", encoding="utf-8")
    res = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}})
    uris = [r.get("uri", "") for r in res.get("result", {}).get("resources", [])]
    # the empty ns entry must be skipped
    assert all("ns=" not in u for u in uris)


def test_ci_validate_project_license_present_verify_raises(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    monkeypatch.setattr(srv, "_license_required", lambda: True)
    proj_lic = tmp_path / ".mcp" / "license.json"
    proj_lic.parent.mkdir(parents=True, exist_ok=True)
    proj_lic.write_text("{}", encoding="utf-8")
    with mock.patch.object(ms, "_verify_license", side_effect=RuntimeError("oops")):
        with pytest.raises(ValueError):
            srv._call_tool("ci.validate", {})
    assert (tmp_path / ".mcp" / "dashboard" / "release_check.md").exists()


def test_project_switch_allow_cfg_exception_path(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)

    class BadCfg:
        def get(self, *a, **k):  # raises when accessing cfg.get("project", {})
            raise RuntimeError("badcfg")

    srv.cfg = BadCfg()
    monkeypatch.delenv("MCP_ALLOW_PROJECT_SWITCH", raising=False)
    monkeypatch.setenv("MCP_STRICT_ISOLATION", "1")
    with pytest.raises(ValueError):
        srv._call_tool("project.switch", {"path": str(tmp_path / "p2")})


def test_coverage_report_defaults_from_config(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)

    def fake_load_config(_root):
        return {"coverage": {"near": {"within": 0.04, "top": 7}}}

    class Stub:
        @staticmethod
        def summarize(project_root, policy, min_module):
            return {"ok": True, "weak": []}

        @staticmethod
        def summarize_groups(project_root, policy, min_module):
            return {"groups": []}

        @staticmethod
        def summarize_near(project_root, policy, min_module, within, top):
            # ensure defaults from config are wired
            assert within == 0.04 and top == 7
            return {"near": []}

    monkeypatch.setattr(ms, "load_config", fake_load_config)
    monkeypatch.setattr(ms, "covsum", Stub)
    out = srv._call_tool("coverage.report", {})
    assert out.get("ok") is True and out.get("near") == [] and out.get("groups") == []
