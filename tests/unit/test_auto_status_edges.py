from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.auto_status as AS


def test_overall_progress_try_except(monkeypatch, tmp_path: Path) -> None:
    # Force coverage snapshot to return a bad progress type to trigger except
    monkeypatch.setattr(
        AS,
        "_coverage_snapshot",
        lambda root=None: {
            "progress": "bad",
            "weak": [],
            "groups": [],
            "near": [],
            "min_module": 0.9,
            "count": 0,
        },
    )
    out = AS.generate_status(project_root=tmp_path)
    assert float(out.get("progress", {}).get("overall", 0.0)) == 0.0


def test_history_not_list_and_loads_error(monkeypatch, tmp_path: Path) -> None:
    # Prepare dashboard and a corrupt (non-list) history file to hit `hist = []` branch
    dash = tmp_path / ".mcp/dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    (dash / "history.json").write_text("{}", encoding="utf-8")
    AS.generate_status(project_root=tmp_path)

    # Now force json.loads to raise to hit the outer except path
    def bad_loads(_s: str):  # type: ignore[no-redef]
        raise ValueError("boom")

    monkeypatch.setattr(AS.json, "loads", lambda *a, **k: bad_loads(""))
    AS.generate_status(project_root=tmp_path)
