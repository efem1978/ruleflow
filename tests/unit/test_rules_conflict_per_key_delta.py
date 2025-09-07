from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_compile_rules_per_key_conflict_delta(tmp_path: Path) -> None:
    # prepare raw items with small delta (3%) for coverage.min_module
    raw = {
        "items": [
            {
                "key": "coverage.min_module",
                "value": 0.90,
                "text": "min module 90%",
                "source": {"file": "a.md", "line": 1},
            },
            {
                "key": "coverage.min_module",
                "value": 0.93,
                "text": "min module 93%",
                "source": {"file": "b.md", "line": 2},
            },
        ]
    }
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/rules_raw.json").write_text(json.dumps(raw), encoding="utf-8")
    # set per-key conflict delta stricter (1%), and default 5%
    (tmp_path / ".mcp/assistant.yaml").write_text(
        "rules:\n  conflict_delta: {coverage.min_module: 0.01, __default__: 0.05}\n",
        encoding="utf-8",
    )
    out = ri.compile_rules(project_root=tmp_path)
    assert out.get("ok", True) is not False
    conflicts = out.get("conflicts", []) or []
    assert any(c.get("key") == "coverage.min_module" for c in conflicts)
    meta = out.get("meta", {}) or {}
    used = meta.get("conflict_delta", {}) or {}
    # per-key threshold should be recorded
    assert float(used.get("coverage.min_module")) == 0.01
