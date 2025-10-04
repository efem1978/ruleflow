from __future__ import annotations

from pathlib import Path

import pytest

from mcp_rules_assistant.dev_agent import (
    DevAgent,
    auto_commit,
    auto_tag,
    get_run_config,
)


def test_auto_commit_and_tag_happy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    # Prepare repo dir structure
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp" / "dashboard").mkdir(parents=True, exist_ok=True)

    # Plan in-progress with a current step (meets auto-commit precondition)
    (tmp_path / ".mcp" / "plan.md").write_text(
        "# Plan\n\n- status: in_progress\n- current step: do X\n",
        encoding="utf-8",
    )

    agent = DevAgent(project_root=tmp_path)

    # Enable auto features via env
    monkeypatch.setenv("DEV_AGENT_AUTOCOMMIT", "1")
    monkeypatch.setenv("DEV_AGENT_AUTOPUSH", "1")
    monkeypatch.setenv("DEV_AGENT_AUTOTAG", "1")

    # Stub subprocess calls for git interactions
    class P:
        def __init__(self, code: int = 0, out: str = "M foo\n") -> None:
            self.returncode = code
            self.stdout = out

    calls = {
        "status": 0,
        "add": 0,
        "commit": 0,
        "push": 0,
        "tag_list": 0,
        "tag_create": 0,
    }

    def fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
        cmd = " ".join(map(str, args))
        if "status --porcelain" in cmd:
            calls["status"] += 1
            return P(0, "M file.py\n")
        if cmd.startswith("git add -A"):
            calls["add"] += 1
            return P(0, "")
        if cmd.startswith("git commit -m"):
            calls["commit"] += 1
            return P(0, "")
        if cmd == "git push":
            calls["push"] += 1
            return P(0, "")
        if cmd.startswith("git tag -l"):
            calls["tag_list"] += 1
            return P(0, "")
        if cmd.startswith("git tag -a"):
            calls["tag_create"] += 1
            return P(0, "")
        return P(0, "")

    monkeypatch.setattr("mcp_rules_assistant.dev_agent.run_cmd", fake_run)

    tests: dict[str, object] = {"ok": True, "mode": "full"}
    bypass: dict[str, object] = {"active": False}
    run_cfg = get_run_config(agent)

    # Ensure commit interval satisfied
    last_commit_ts = 0.0

    # Build a status with no weak coverage, lint/type ok
    status: dict[str, object] = {
        "coverage": {"weak": []},
        "checks": {"lint": "ok", "type": "ok"},
    }

    # Auto-commit
    last_commit_ts = auto_commit(agent, tests, bypass, run_cfg, last_commit_ts)

    # Auto-tag
    last_tag = auto_tag(agent, tests, status, run_cfg, "")

    # Validate interactions happened
    assert calls["status"] >= 1
    assert calls["add"] >= 1
    assert calls["commit"] >= 1
    assert calls["push"] >= 1
    assert isinstance(last_tag, str)
