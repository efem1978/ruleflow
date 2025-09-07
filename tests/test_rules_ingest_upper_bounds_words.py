from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_upper_bound_english_words_core(tmp_path: Path) -> None:
    d = tmp_path / "ub_words1.md"
    d.write_text("- core at most ninety five percent", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    comp = res.get("compiled") or {}
    sugg = comp.get("suggestions") or []
    assert any(
        (s.get("key") == "coverage.max_core" and s.get("action") == "monitor")
        for s in sugg
    )


def test_upper_bound_english_words_module(tmp_path: Path) -> None:
    d = tmp_path / "ub_words2.md"
    d.write_text("- no more than ninety percent coverage", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    comp = res.get("compiled") or {}
    sugg = comp.get("suggestions") or []
    assert any(
        (s.get("key") == "coverage.max_module" and s.get("action") == "monitor")
        for s in sugg
    )
