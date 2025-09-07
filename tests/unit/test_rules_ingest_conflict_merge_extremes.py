from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_numeric_close_values_keep_stricter_without_conflict(tmp_path: Path) -> None:
    raw = {
        "items": [
            {
                "key": "coverage.min_core",
                "value": 0.960,
                "text": "a",
                "source": {"file": "a.md", "line": 1},
            },
            {
                "key": "coverage.min_core",
                "value": 0.961,
                "text": "b",
                "source": {"file": "b.md", "line": 2},
            },
        ]
    }
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/rules_raw.json").write_text(json.dumps(raw), encoding="utf-8")
    out = ri.compile_rules(project_root=tmp_path)
    pol = out.get("policy") or {}
    # 应保留更严格值（0.961）且无冲突（接近值 < 默认5%）
    assert abs(float(pol.get("coverage.min_core")) - 0.961) < 1e-6
    assert not out.get("conflicts")


def test_boolean_conflict_detected_and_stricter_kept(tmp_path: Path) -> None:
    raw = {
        "items": [
            {
                "key": "test.no_skip_xfail",
                "value": False,
                "text": "a",
                "source": {"file": "a.md", "line": 1},
            },
            {
                "key": "test.no_skip_xfail",
                "value": True,
                "text": "b",
                "source": {"file": "b.md", "line": 2},
            },
        ]
    }
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/rules_raw.json").write_text(json.dumps(raw), encoding="utf-8")
    out = ri.compile_rules(project_root=tmp_path)
    pol = out.get("policy") or {}
    assert pol.get("test.no_skip_xfail") is True
    assert any(
        c.get("key") == "test.no_skip_xfail" for c in (out.get("conflicts") or [])
    )
