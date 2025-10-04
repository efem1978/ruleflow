"""Batch A: broaden mcp_server coverage to remaining branches."""
from __future__ import annotations

import json
import sys
from types import ModuleType
from pathlib import Path
from unittest import mock

import pytest

import mcp_rules_assistant.mcp_server as ms
from mcp_rules_assistant.mcp_server import JsonRpcServer


def _srv(tmp_path: Path, monkeypatch) -> JsonRpcServer:
    monkeypatch.chdir(tmp_path)
    return JsonRpcServer()


def test_call_tool_refresh_guard_import_error(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    # Force refresh branch
    srv._cfg_root = tmp_path / "other"
    # Inject fake module without MemoryManager so 'from .memory import MemoryManager' raises
    fake = ModuleType("mcp_rules_assistant.memory")
    monkeypatch.setitem(sys.modules, "mcp_rules_assistant.memory", fake)
    # Call any tool to trigger refresh path
    # Choose a simple tool to avoid heavy behavior
    with mock.patch.object(srv, "_tool_rules_maxima", return_value={"ok": True}):
        out = srv._call_tool("rules.maxima", {})
    assert out == {"ok": True}


def test_project_switch_add_link_exceptions(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    # Make add_link raise for both switched_to and switched_from
    class DummyMM:
        def __init__(self):
            self.calls = 0
        def add_link(self, *a, **k):
            self.calls += 1
            raise RuntimeError("add_link fail")
    srv.mm = DummyMM()
    newp = tmp_path / "newproj"
    res = srv._call_tool("project.switch", {"path": str(newp)})
    assert res.get("ok") is True and Path(res.get("root")).resolve() == newp.resolve()


def test_project_link_write_disabled(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    monkeypatch.setattr(srv, "_memory_write_allowed", lambda: False)
    out = srv._call_tool("project.link", {"project": "p", "task": "t", "note": "n"})
    assert out == {"ok": False, "error": "memory_write_disabled"}


def test_memory_append_turn_allowed_audit_exception(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    monkeypatch.setattr(srv, "_memory_write_allowed", lambda: True)
    # Provide a lightweight MemoryManager stub
    class MM:
        def append_turn(self, *a, **k):
            return None
    srv.mm = MM()
    with mock.patch.object(ms, "_audit", side_effect=RuntimeError("audit fail")):
        out = srv._call_tool("memory.append_turn", {"role": "u", "content": "x", "meta": {}})
    assert out == {"ok": True}


def test_rules_resolve_compiled_json_read_error(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    pjson = srv.project_root / ms.ri.COMPILED_JSON
    pjson.parent.mkdir(parents=True, exist_ok=True)
    pjson.write_text("{}", encoding="utf-8")
    with mock.patch.object(Path, "read_text", side_effect=lambda self, *a, **k: (_ for _ in ()).throw(OSError("boom")) if self == pjson else Path.read_text.__wrapped__(self, *a, **k)):  # type: ignore[attr-defined]
        with mock.patch.object(srv, "_tool_rules_enforce", return_value={}):
            out = srv._call_tool("rules.resolve", {})
    assert isinstance(out, dict)


def test_fs_apply_disallow_patterns_flag_parse_exception(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    srv.cfg = {"execution": {"disallow_patterns": ["BAD"], "disallow_patterns_hard": False}}
    # Any exception from _get_exec_flag should be swallowed and treated as False
    with mock.patch.object(srv, "_get_exec_flag", side_effect=RuntimeError("x")):
        out = srv._call_tool(
            "fs.apply_patch",
            {
                "files": [{"path": "a.py", "content": "BAD"}],
                "runChecks": True,
                "strict": True,
                "dryRun": True,
            },
        )
    assert out.get("ok") is True


def test_fs_apply_max_content_bytes_parse_fallback(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    srv.cfg = {"execution": {"allowed_write_prefixes": ["x/"], "max_content_bytes": "X"}}
    out = srv._call_tool(
        "fs.apply_patch",
        {
            "files": [{"path": "x/a.txt", "content": "123"}],
            "runChecks": False,
            "strict": False,
            "dryRun": False,
        },
    )
    assert out.get("ok") is True


def test_res_read_memory_symlink_inside_disallowed(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    mcp = tmp_path / ".mcp"
    mcp.mkdir(exist_ok=True)
    target = mcp / "real.json"
    target.write_text("{}", encoding="utf-8")
    nsf = mcp / "memory.s.json"
    nsf.symlink_to(target)
    with pytest.raises(FileNotFoundError):
        srv._res_read_memory(f"memory://{srv._project_id()}/rollup?ns=s")


def test_res_read_memory_is_relative_to_exception_fallback(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    mcp = tmp_path / ".mcp"
    mcp.mkdir(exist_ok=True)
    fn = mcp / "memory.ok.json"
    fn.write_text("{\"turns\":[],\"summary\":\"\",\"links\":[]}", encoding="utf-8")
    # Make is_relative_to raise so fallback path is used
    original = Path.is_relative_to
    def broken_is_rel(self, *a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(Path, "is_relative_to", broken_is_rel, raising=True)
    out = srv._res_read_memory(f"memory://{srv._project_id()}/rollup?ns=ok")
    assert out.get("mimeType") == ms.MIME_JSON


def test_res_read_memory_safety_generic_exception(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    mcp = tmp_path / ".mcp"
    mcp.mkdir(exist_ok=True)
    fn = mcp / "memory.x.json"
    fn.write_text("{}", encoding="utf-8")
    # Make resolve raise to trigger generic exception -> FileNotFoundError
    original_resolve = Path.resolve
    def bad_resolve(self):
        if self == fn:
            raise OSError("xx")
        return original_resolve(self)
    monkeypatch.setattr(Path, "resolve", bad_resolve, raising=True)
    with pytest.raises(FileNotFoundError):
        srv._res_read_memory(f"memory://{srv._project_id()}/rollup?ns=x")


def test_coverage_near_and_report_tools(tmp_path: Path, monkeypatch):
    srv = _srv(tmp_path, monkeypatch)
    # stub covsum functions
    class Stub:
        @staticmethod
        def summarize(project_root, policy, min_module):
            return {"ok": True, "weak": []}
        @staticmethod
        def summarize_groups(project_root, policy, min_module):
            return {"groups": []}
        @staticmethod
        def summarize_near(project_root, policy, min_module, within, top):
            return {"near": []}
    monkeypatch.setattr(ms, "covsum", Stub)
    out1 = srv._call_tool("coverage.near", {"within": 0.05, "top": 3})
    assert out1 == {"near": []}
    out2 = srv._call_tool("coverage.report", {"within": 0.05, "top": 3})
    assert out2.get("ok") is True and "groups" in out2 and "near" in out2
