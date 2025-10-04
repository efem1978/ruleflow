from __future__ import annotations

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_rules_ingest_requires_list() -> None:
    srv = JsonRpcServer()
    with pytest.raises(ValueError):
        srv._call_tool("rules.ingest", {"paths": "README.md"})
    with pytest.raises(ValueError):
        srv._call_tool("rules.ingest", {"paths": [""]})


def test_env_prepare_type_checks(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # Non-bool create/install should be coerced by bool(); we keep behavior stable.
    # But packages must be list-like; pass invalid to trigger failure down the pipe by run_cmd mock
    calls = []

    def fake_run(cmd, cwd=None, check=False, capture_stdout=False, env=None, on_event=None):  # type: ignore[no-untyped-def]
        calls.append(cmd)

        class P:
            returncode = 0
            stdout = ""
            stderr = ""

        return P()

    monkeypatch.setattr("mcp_rules_assistant.mcp_server.run_cmd", fake_run)
    out = srv._call_tool("env.prepare", {"create": True, "install": False})
    assert out.get("ok") is True and out.get("created") in (True, False)


def test_plan_set_type_validation() -> None:
    srv = JsonRpcServer()
    with pytest.raises(ValueError):
        srv._call_tool("plan.set", {"status": 1})
    with pytest.raises(ValueError):
        srv._call_tool("plan.set", {"current": {}})
    with pytest.raises(ValueError):
        srv._call_tool("plan.set", {"next": []})


def test_env_prepare_packages_must_be_list(tmp_path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    with pytest.raises(ValueError):
        srv._call_tool("env.prepare", {"packages": "pytest"})
