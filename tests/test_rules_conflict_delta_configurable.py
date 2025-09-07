from __future__ import annotations

from pathlib import Path

import yaml

from mcp_rules_assistant import rules_ingest as ri


def test_conflict_delta_from_config(tmp_path: Path) -> None:
    # Default: 90 vs 94 (diff 0.04) — no conflict (already covered elsewhere)
    # Now set conflict_delta=0.03 to force conflict
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    y = {"rules": {"conflict_delta": 0.03}}
    cfg.write_text(
        yaml.safe_dump(y, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("- 覆盖率 90%", encoding="utf-8")
    b.write_text("- 覆盖率 94%", encoding="utf-8")
    res = ri.ingest([str(a), str(b)], project_root=tmp_path)
    compiled = res.get("compiled") or {}
    conflicts = compiled.get("conflicts") or []
    assert any(c.get("key") == "coverage.min_module" for c in conflicts)
