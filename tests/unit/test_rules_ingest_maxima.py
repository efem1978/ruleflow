from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_maxima_aggregates_and_keeps_stricter(tmp_path: Path) -> None:
    raw = {
        "items": [
            {
                "key": "coverage.max_module",
                "value": 0.99,
                "text": "max module",
                "source": {"file": "a.md", "line": 1},
            },
            {
                "key": "coverage.max_module",
                "value": 0.97,
                "text": "max module lower",
                "source": {"file": "b.md", "line": 2},
            },
        ],
    }
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/rules_raw.json").write_text(json.dumps(raw), encoding="utf-8")
    out = ri.compile_rules(project_root=tmp_path)
    assert out.get("ok", True) is not False
    meta = out.get("meta") or {}
    maxima = meta.get("maxima") or {}
    assert float(maxima.get("coverage.max_module")) == 0.97


def test_english_words_clamp_over_100() -> None:
    # 101+ should clamp to 100 in english words parser
    v = ri._english_words_to_int("one hundred and twenty")
    assert v == 100
