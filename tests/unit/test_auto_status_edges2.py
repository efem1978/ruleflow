from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.auto_status as auto_status


def test_cov_progress_exception_fallback(monkeypatch, tmp_path: Path) -> None:
    # Force summarize() to return a bad count type to hit exception branch
    def fake_sum(**kwargs):  # type: ignore[no-untyped-def]
        return {"weak": [], "count": "bad"}

    def fake_groups(**kwargs):  # type: ignore[no-untyped-def]
        return {"groups": []}

    def fake_near(**kwargs):  # type: ignore[no-untyped-def]
        return {"near": []}

    monkeypatch.setattr(auto_status.cov, "summarize", fake_sum)
    monkeypatch.setattr(auto_status.cov, "summarize_groups", fake_groups)
    monkeypatch.setattr(auto_status.cov, "summarize_near", fake_near)

    out = auto_status.generate_status(project_root=tmp_path)
    cov = out.get("coverage") or {}
    assert cov.get("progress") == 0.0


def test_cmd_metrics_read_error(tmp_path: Path) -> None:
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    # Make a directory with the same name as the expected JSONL file to trigger read error
    (dash / "cmd_events.jsonl").mkdir()
    out = auto_status.generate_status(project_root=tmp_path)
    assert "cmd_metrics" not in out
