from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.auto_status import generate_status


def test_auto_status_cmd_metrics(tmp_path: Path) -> None:
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    jl = dash / "cmd_events.jsonl"
    # write a few end/error events
    recs = [
        {"phase": "start", "cwd": str(tmp_path), "attempt": 0},
        {"phase": "end", "cwd": str(tmp_path), "attempt": 0, "elapsed": 0.12},
        {"phase": "error", "cwd": str(tmp_path), "attempt": 0, "exception": "X"},
    ]
    jl.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    out = generate_status(project_root=tmp_path)
    cm = out.get("cmd_metrics") or {}
    last = (cm.get("last24h") or {}) if isinstance(cm, dict) else {}
    # best-effort presence checks
    assert "events" in last and "avg_elapsed" in last and "fail_ratio" in last
