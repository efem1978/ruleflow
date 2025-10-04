from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from unittest import mock

import pytest

import mcp_rules_assistant.dev_agent as da


def _agent(tmp_path: Path, monkeypatch) -> da.DevAgent:
    monkeypatch.chdir(tmp_path)
    return da.DevAgent(project_root=tmp_path)


def test_instance_run_tests_with_coverage_venv_path_and_typeerror(tmp_path: Path, monkeypatch):
    ag = _agent(tmp_path, monkeypatch)
    # ensure .mcp/venv/bin exists to set PATH (line ~99)
    (tmp_path / ".mcp" / "venv" / "bin").mkdir(parents=True, exist_ok=True)

    calls = {"n": 0}

    def fake_run_cmd(cmd, *, cwd, capture_stdout=True, env=None, on_event=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TypeError("on_event not accepted")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(da, "run_cmd", fake_run_cmd)
    out = ag._run_tests_with_coverage(on_event=lambda e: None)
    assert out["ok"] is True and out["code"] == 0 and "cmd" in out


def test_module_run_tests_with_coverage_venv_path(tmp_path: Path, monkeypatch):
    (tmp_path / ".mcp" / "venv" / "bin").mkdir(parents=True, exist_ok=True)

    def fake_run_cmd(cmd, *, cwd, capture_stdout=True, env=None, on_event=None):
        return SimpleNamespace(returncode=0, stdout="S", stderr="")

    monkeypatch.setattr(da, "run_cmd", fake_run_cmd)
    out = da._run_tests_with_coverage(tmp_path)
    assert out["ok"] is True and out["code"] == 0


def test_update_failure_and_freeze_status_and_brief_excepts(tmp_path: Path, monkeypatch):
    ag = _agent(tmp_path, monkeypatch)
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)

    # Status dict that triggers: freeze activation (via env thresholds),
    # _read_json exception path, progress/coverage/timestamp conversion excepts
    class BadDict(dict):
        def get(self, *a, **k):
            if a and a[0] == "weak":
                raise RuntimeError("boom")
            return super().get(*a, **k)

    # Prepare status with minimal fields
    status: dict[str, Any] = {
        "checks": {da.STEP_LINT: "ok", da.STEP_TYPE: "skipped", da.STEP_TESTS: "fail"},
        "tests": {"ok": False, "code": 2, "mode": "full"},
        "coverage": {"weak": BadDict()},  # weak get will raise → weak_len except
        "progress": {"overall": "bad"},  # overall float conversion except
        "timestamp": object(),  # float(object()) → except
    }

    # Low thresholds to activate freeze immediately
    monkeypatch.setenv("DEV_AGENT_THR_TESTS", "0")
    monkeypatch.setenv("DEV_AGENT_THR_BUILD", "0")
    monkeypatch.setenv("DEV_AGENT_THR_SEVERE", "0")

    # Force _read_json to raise only for status.json to hit debug except at ~659-660
    def read_json_side(p: Path):
        return (_ for _ in ()).throw(RuntimeError("xx")) if p.name == da.STATUS_FILE else {}

    with mock.patch.object(ag, "_read_json", side_effect=read_json_side):
        ag._update_failure_and_freeze_status(status, dash)

    # Brief file should be written despite exceptions
    brief = json.loads((dash / "status_brief.json").read_text(encoding="utf-8"))
    assert set(brief.keys()) == {"overall", "weak_count", "timestamp"}


def test_auto_append_memory_hard_disable(tmp_path: Path, monkeypatch):
    ag = _agent(tmp_path, monkeypatch)
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)

    # Enable feature and remove rate-limit
    monkeypatch.setenv("DEV_AGENT_MEM_ENABLE", "1")
    monkeypatch.setenv("DEV_AGENT_MEM_MIN_SEC", "0")

    # load_config returns hard_disable → early False (line ~838)
    def fake_load_cfg(root):
        return {"memory": {"hard_disable": True}}

    with mock.patch("mcp_rules_assistant.config.load_config", fake_load_cfg):
        ok = ag._auto_append_memory({"plan": {}, "coverage": {}, "progress": {}}, dash)
    assert ok is False


def test_auto_append_memory_strict_and_pytest_env_get_exception(tmp_path: Path, monkeypatch):
    ag = _agent(tmp_path, monkeypatch)
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DEV_AGENT_MEM_ENABLE", "1")
    monkeypatch.setenv("DEV_AGENT_MEM_MIN_SEC", "0")
    monkeypatch.setenv("MCP_STRICT_ISOLATION", "1")

    # load_config raises → allow_cfg False (lines ~840-841)
    with mock.patch("mcp_rules_assistant.config.load_config", side_effect=RuntimeError("x")):
        # Proxy environ.get to raise only for PYTEST_CURRENT_TEST to hit except at ~846-847
        orig_env = da.os.environ

        class EnvProxy:
            def get(self, key, default=None):
                if key == "PYTEST_CURRENT_TEST":
                    raise RuntimeError("boom")
                return orig_env.get(key, default)

        monkeypatch.setattr(da, "os", SimpleNamespace(environ=EnvProxy()))
        ok = ag._auto_append_memory({"plan": {}, "coverage": {}, "progress": {}}, dash)
        assert ok is False  # strict + not allowed


def test_auto_append_memory_strict_off_returns_false(tmp_path: Path, monkeypatch):
    ag = _agent(tmp_path, monkeypatch)
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DEV_AGENT_MEM_ENABLE", "1")
    monkeypatch.setenv("DEV_AGENT_MEM_MIN_SEC", "0")
    monkeypatch.delenv("MCP_STRICT_ISOLATION", raising=False)

    # Ensure test-only env isn't elevating allow_cfg
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with mock.patch("mcp_rules_assistant.config.load_config", side_effect=RuntimeError("x")):
        ok = ag._auto_append_memory({"plan": {}, "coverage": {}, "progress": {}}, dash)
        assert ok is False  # not allowed, strict off → line ~855


def test_run_calls_instance_ensure_dashboard_dir_when_module_stubbed(tmp_path: Path, monkeypatch):
    ag = _agent(tmp_path, monkeypatch)

    # Stub module-level _ensure_dashboard_dir to a non-callable to take the else path (line ~1052)
    monkeypatch.setattr(da, "_ensure_dashboard_dir", None, raising=True)

    # Minimal stubs to avoid heavy operations in run()
    monkeypatch.setattr(da.DevAgent, "_ensure_dashboard_dir", lambda self, rebuild=False: (self.project_root / ".mcp" / "dashboard"))
    monkeypatch.setattr(da.DevAgent, "_run_impacted_or_full", lambda self, **k: {"ok": True, "code": 0, "mode": "full"})
    monkeypatch.setattr(da.DevAgent, "_run_cycle_checks", lambda self, **k: {"lint": "ok", "type": "skipped", "tdd": "ok"})
    monkeypatch.setattr(da.DevAgent, "_update_bypass_status", lambda self, t, rc: (t, {"active": False}))
    monkeypatch.setattr(da.DevAgent, "_persist_status_and_history", lambda self, *a, **k: None)
    monkeypatch.setattr(da.DevAgent, "_auto_append_memory", lambda self, *a, **k: False)
    monkeypatch.setattr(da.DevAgent, "_handle_auto_commit", lambda self, *a, **k: 0.0)
    monkeypatch.setattr(da.DevAgent, "_handle_auto_tag", lambda self, *a, **k: "")
    monkeypatch.setattr(time, "sleep", lambda s: None)

    ag.run(interval=1, max_cycles=1)


def test_collect_tasks_counts_exception_fallback(tmp_path: Path, monkeypatch):
    # Force exception inside function to hit except at ~1488-1489
    with mock.patch("mcp_rules_assistant.dev_agent._scan_markdown_checklist", side_effect=RuntimeError("boom")):
        done, pend, pitems, ditems = da._collect_tasks_counts(tmp_path, "")
        assert done == 0 and pend == 0 and pitems == [] and ditems == []
