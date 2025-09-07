from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_per_key_conflict_delta(tmp_path: Path) -> None:
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        "\n".join(
            [
                "rules:",
                "  conflict_delta:",
                "    coverage.min_module: 0.05",
                "    coverage.min_core: 0.02",
            ]
        ),
        encoding="utf-8",
    )
    # Module: 90 vs 94 (diff 0.04) — threshold 0.05 => no conflict
    # Core: 95 vs 98 (diff 0.03) — threshold 0.02 => conflict
    m1 = tmp_path / "m1.md"
    m1.write_text("- 覆盖率 90%", encoding="utf-8")
    m2 = tmp_path / "m2.md"
    m2.write_text("- 覆盖率 94%", encoding="utf-8")
    c1 = tmp_path / "c1.md"
    c1.write_text("- 核心 95%", encoding="utf-8")
    c2 = tmp_path / "c2.md"
    c2.write_text("- 核心 98%", encoding="utf-8")
    res = ri.ingest([str(m1), str(m2), str(c1), str(c2)], project_root=tmp_path)
    compiled = res.get("compiled") or {}
    conflicts = compiled.get("conflicts") or []
    # module not in conflicts
    assert not any(c.get("key") == "coverage.min_module" for c in conflicts)
    # core in conflicts
    assert any(c.get("key") == "coverage.min_core" for c in conflicts)
    meta = (compiled.get("meta") or {}).get("conflict_delta") or {}
    # meta should record used thresholds
    assert float(meta.get("coverage.min_module", 0.0)) == 0.05
    assert float(meta.get("coverage.min_core", 0.0)) == 0.02
