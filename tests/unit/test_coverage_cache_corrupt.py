from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.coverage_summary as cs


def test_corrupted_cache_does_not_break_summary(tmp_path: Path) -> None:
    xml = (
        '<coverage line-rate="1.0" branch-rate="0" version="1" timestamp="0">'
        '<packages><package name="p"><classes>'
        '<class filename="x.py" line-rate="0.99" lines-valid="10" lines-covered="10"/>'
        "</classes></package></packages></coverage>"
    )
    (tmp_path / "coverage.xml").write_text(xml, encoding="utf-8")
    # write corrupted cache
    cache = tmp_path / ".mcp/coverage_cache.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("{not: json", encoding="utf-8")
    out = cs.summarize(project_root=tmp_path, policy=None, min_module=0.9)
    assert out.get("ok") is True
    assert out.get("count") == 1
