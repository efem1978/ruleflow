from __future__ import annotations

from pathlib import Path

import pytest

import mcp_rules_assistant.dev_agent as dev_agent
import mcp_rules_assistant.dev_agent as dev_agent_module
from mcp_rules_assistant.dev_agent import DevAgent, update_failure_and_freeze


def test_persist_fail_counters_write_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)

    agent = DevAgent(project_root=tmp_path)

    # Prepare a failing status to exercise counters path; exact values don't matter
    status = {
        "tests": {"ok": False, "code": 2, "mode": "full"},
        "checks": {"lint": "fail", "type": "ok", "tdd": "skipped"},
        "coverage": {"weak": ["a"], "count": 1},
        "progress": {"overall": 0.0},
    }

    # Intercept atomic writes for fail_counters.json only and make it raise
    orig_atomic = dev_agent.atomic_write_text

    def boom_atomic(p: Path, content: str, encoding: str = "utf-8") -> None:  # type: ignore[override]
        if p.name == "fail_counters.json":
            raise OSError("deny")
        return orig_atomic(p, content, encoding)

    monkeypatch.setattr(dev_agent, "atomic_write_text", boom_atomic)

    # Should not raise despite write failure; file should not be created
    out = update_failure_and_freeze(agent, dict(status), dash)
    assert isinstance(out, dict)
    assert not (dash / "fail_counters.json").exists()


def test_freeze_threshold_boundary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    agent = DevAgent(project_root=tmp_path)

    # Only tests threshold active at 2; others high to avoid accidental triggers
    monkeypatch.setenv("DEV_AGENT_THR_TESTS", "2")
    monkeypatch.setenv("DEV_AGENT_THR_BUILD", "99")
    monkeypatch.setenv("DEV_AGENT_THR_SEVERE", "99")

    failing = {
        "tests": {"ok": False, "code": 2, "mode": "full"},
        # mark tests gate as fail so tests counter increments
        "checks": {"tests": "fail", "lint": "ok", "type": "ok", "tdd": "skipped"},
        "coverage": {"weak": ["a"], "count": 1},
        "progress": {"overall": 0.0},
    }

    # First failure (count=1 < thr=2): should NOT freeze
    st1 = update_failure_and_freeze(agent, dict(failing), dash)
    assert st1.get("freeze", {}).get("active") in (False, None)

    # Second failure (count=2 == thr): should freeze now
    st2 = update_failure_and_freeze(agent, dict(failing), dash)
    assert st2.get("freeze", {}).get("active") is True


def test_quick_status_check_exception_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = DevAgent(project_root=tmp_path)

    class P:
        def __init__(self, rc: int = 0, out: str = "") -> None:
            self.returncode = rc
            self.stdout = out
            self.stderr = ""

    def fake_run_cmd(
        cmd: list[str],
        *,
        cwd: Path,
        capture_stdout: bool = True,
        env=None,
        check: bool = False,
    ):  # noqa: ANN001
        if cmd and cmd[0] == "ruff":
            return P(0)
        if cmd and cmd[0] == "mypy":
            raise RuntimeError("mypy missing")
        if cmd and cmd[0] == "python":
            return P(0)
        return P(0)

    monkeypatch.setattr(dev_agent_module, "run_cmd", fake_run_cmd)

    checks = agent._run_cycle_checks()
    assert checks.get("lint") == "ok"
    assert checks.get("type") == "skipped"
