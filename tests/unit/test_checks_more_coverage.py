from __future__ import annotations

import os
import types
from pathlib import Path

from mcp_rules_assistant import checks


def test_use_process_runner_env_off_bypasses_config(
    monkeypatch, tmp_path: Path
) -> None:
    # Ensure cache cleared
    monkeypatch.setattr(checks, "_USE_PROC_RUNNER_CACHE", None)
    # Force env to explicit off
    monkeypatch.setenv("MCP_CHECKS_PROCESS_RUNNER", "0")
    # Make _load_cfg raise to verify it doesn't matter when env off
    monkeypatch.setattr(
        checks,
        "_load_cfg",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("no cfg")),
    )
    assert checks._use_process_runner(tmp_path) is False


def test_use_process_runner_config_exception(monkeypatch, tmp_path: Path) -> None:
    # Clear cache and env
    monkeypatch.delenv("MCP_CHECKS_PROCESS_RUNNER", raising=False)
    monkeypatch.setattr(checks, "_USE_PROC_RUNNER_CACHE", None)
    # _load_cfg raises -> except path sets use=False
    monkeypatch.setattr(
        checks,
        "_load_cfg",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert checks._use_process_runner(tmp_path) is False


def test_run_process_runner_raises_fallback_to_subprocess(
    monkeypatch, tmp_path: Path
) -> None:
    # Turn on process runner via env
    monkeypatch.setenv("MCP_CHECKS_PROCESS_RUNNER", "1")

    # Force _proc_run_cmd to raise generic Exception -> triggers fallback 'pass' branch
    def bad_run(*_a, **_k):  # noqa: ANN001
        raise RuntimeError("proc error")

    monkeypatch.setattr(checks, "_proc_run_cmd", bad_run)

    class P:
        def __init__(self):
            self.returncode = 0
            self.stdout = "ok"
            self.stderr = ""

    # Provide a subprocess.run replacement to avoid invoking real commands
    monkeypatch.setattr(
        checks,
        "subprocess",
        types.SimpleNamespace(run=lambda *a, **k: P()),
        raising=True,
    )
    out = checks._run(["echo", "hi"], cwd=tmp_path)
    assert (
        out.get("ok") is True
        and out.get("code") == 0
        and (out.get("stdout") or "").startswith("ok")
    )
