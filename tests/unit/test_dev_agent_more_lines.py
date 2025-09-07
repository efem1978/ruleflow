from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import dev_agent as dev_mod


def test_dev_agent_compute_status_plan_read_error(monkeypatch, tmp_path: Path) -> None:
    agent = dev_mod.DevAgent(project_root=tmp_path)
    # Force read_plan to raise to cover exception branch (lines ~194-195)
    monkeypatch.setattr(dev_mod, "read_plan", lambda *_args, **_kw: (_ for _ in ()).throw(RuntimeError("boom")))  # type: ignore[no-untyped-call]
    # Coverage of fallback should not raise
    st = agent.compute_status()
    assert isinstance(st, dict)
    assert isinstance(st.get("coverage", {}), dict)
    assert "progress" in st.get("coverage", {})
