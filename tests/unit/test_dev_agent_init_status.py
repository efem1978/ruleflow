from __future__ import annotations

import json
import types
from pathlib import Path

from mcp_rules_assistant.dev_agent import DevAgent


def test_initialize_run_status_writes_files(tmp_path: Path, monkeypatch) -> None:
    a = DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp/dashboard"
    dash.mkdir(parents=True, exist_ok=True)

    # Monkeypatch heavy methods to fast fakes
    def _fake_run_impacted_or_full(self, cycle_idx: int, full_every: int = 1, on_event=None):  # type: ignore[no-redef]
        return {"ok": True, "code": 0, "stdout": "", "stderr": "", "mode": "full"}

    def _fake_compute_status(self):  # type: ignore[no-redef]
        return {
            "plan": {"status": "in_progress", "current": "X"},
            "coverage": {"weak": []},
            "progress": {"overall": 0.5},
        }

    monkeypatch.setattr(
        a, "_run_impacted_or_full", types.MethodType(_fake_run_impacted_or_full, a)
    )
    monkeypatch.setattr(a, "compute_status", types.MethodType(_fake_compute_status, a))

    a._initialize_run_status(dash, 60)  # type: ignore[attr-defined]
    st = json.loads((dash / "status.json").read_text(encoding="utf-8"))
    assert st.get("interval") == 60 and isinstance(st.get("tests"), dict)
