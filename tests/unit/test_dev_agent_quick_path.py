from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import dev_agent as dev_mod


def test_dev_agent_quick_path(monkeypatch, tmp_path: Path) -> None:
    agent = dev_mod.DevAgent(project_root=tmp_path)

    # Pretend there are changed files
    monkeypatch.setattr(agent, "_git_changed_files", lambda **_: [tmp_path / "x.py"])  # type: ignore[no-untyped-call]

    # Force quick tests to be chosen and succeed
    def fake_quick(files, cwd):  # type: ignore[no-untyped-def]
        return {"ok": True, "skipped": False}

    monkeypatch.setattr(dev_mod.checks, "run_quick_tests", fake_quick)

    res = agent._run_impacted_or_full(cycle_idx=1, full_every=5)
    assert res.get("mode") == "quick" and res.get("ok") is True

