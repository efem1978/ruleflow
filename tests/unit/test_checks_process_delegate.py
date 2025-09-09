from __future__ import annotations

import os
from types import SimpleNamespace


def test_checks_run_uses_process_runner_when_enabled(monkeypatch, tmp_path):
    # Enable delegation via env
    monkeypatch.setenv("MCP_CHECKS_PROCESS_RUNNER", "1")
    import importlib

    import mcp_rules_assistant.checks as checks

    # reset cache to re-evaluate
    checks._USE_PROC_RUNNER_CACHE = None  # type: ignore[attr-defined]

    called = {}

    def _stub_run_cmd(
        cmd, *, cwd, capture_stdout=True, env=None, check=False, **kw
    ):  # noqa: ARG001
        called["cmd"] = list(cmd)
        return SimpleNamespace(returncode=0, stdout="stub", stderr="")

    # Substitute process runner
    monkeypatch.setattr(checks, "_proc_run_cmd", _stub_run_cmd, raising=True)

    out = checks._run(["whatever"], cwd=tmp_path)
    assert out["ok"] is True
    assert out["code"] == 0
    assert called["cmd"] == ["whatever"]


def test_checks_run_fallback_skipped_on_missing_binary(monkeypatch, tmp_path):
    # Disable delegation
    monkeypatch.delenv("MCP_CHECKS_PROCESS_RUNNER", raising=False)
    import mcp_rules_assistant.checks as checks

    checks._USE_PROC_RUNNER_CACHE = None  # type: ignore[attr-defined]

    # Use a clearly missing command to trigger FileNotFoundError path
    out = checks._run(["__definitely_missing_binary__"], cwd=tmp_path)
    assert out.get("skipped") is True
    assert "reason" in out
